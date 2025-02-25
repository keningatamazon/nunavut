/*
 * Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Validates the VariableLengthArray container type using various allocators.
 */

#include "gmock/gmock.h"
#include "nunavut/support/variable_length_array.hpp"
#include <memory>
#include <type_traits>
#include <limits>
#include "o1heap/o1heap.h"
#include <string>
#include <array>
#include <stdexcept>

/**
 * Used to test that destructors were called.
 */
class Doomed
{
public:
    Doomed(int* out_signal_dtor)
        : out_signal_dtor_(out_signal_dtor)
        , moved_(false)
    {
    }
    Doomed(Doomed&& from) noexcept
        : out_signal_dtor_(from.out_signal_dtor_)
        , moved_(false)
    {
        from.moved_ = true;
    }
    Doomed(const Doomed&)            = delete;
    Doomed& operator=(const Doomed&) = delete;
    Doomed& operator=(Doomed&&)      = delete;

    ~Doomed()
    {
        if (!moved_)
        {
            (*out_signal_dtor_) += 1;
        }
    }

private:
    int* out_signal_dtor_;
    bool moved_;
};

/**
 * Pavel's O(1) Heap Allocator wrapped in an std::allocator concept.
 *
 * Note that this implementation probably wouldn't work in a real application
 * because it is not copyable.
 */
template <typename T, std::size_t SizeCount>
class O1HeapAllocator
{
public:
    using value_type = T;

    O1HeapAllocator()
        : heap_()
        , heap_alloc_(o1heapInit(&heap_[0], SizeCount * sizeof(T), nullptr, nullptr))
    {
    }

    O1HeapAllocator(const O1HeapAllocator&)            = delete;
    O1HeapAllocator& operator=(const O1HeapAllocator&) = delete;
    O1HeapAllocator(O1HeapAllocator&&)                 = delete;
    O1HeapAllocator& operator=(O1HeapAllocator&&)      = delete;

    T* allocate(std::size_t n)
    {
        return reinterpret_cast<T*>(o1heapAllocate(heap_alloc_, n * sizeof(T)));
    }

    constexpr void deallocate(T* p, std::size_t n)
    {
        (void) n;
        o1heapFree(heap_alloc_, p);
    }

private:
    typename std::aligned_storage<sizeof(T), O1HEAP_ALIGNMENT>::type heap_[SizeCount];
    O1HeapInstance*                                                  heap_alloc_;
};

/**
 * A Junky static allocator.
 */
template <typename T, std::size_t SizeCount>
class JunkyStaticAllocator
{
public:
    using value_type          = T;
    using array_constref_type = const T (&)[SizeCount];

    JunkyStaticAllocator()
        : data_()
        , alloc_count_(0)
        , last_alloc_size_(0)
        , last_dealloc_size_(0)
    {
    }

    JunkyStaticAllocator(const JunkyStaticAllocator& rhs)
        : data_()
        , alloc_count_(rhs.alloc_count_)
        , last_alloc_size_(rhs.last_alloc_size_)
        , last_dealloc_size_(rhs.last_dealloc_size_)
    {
    }

    T* allocate(std::size_t n)
    {
        if (n <= SizeCount)
        {
            ++alloc_count_;
            last_alloc_size_ = n;
            return reinterpret_cast<T*>(&data_[0]);
        }
        else
        {
            return nullptr;
        }
    }

    constexpr void deallocate(T* p, std::size_t n)
    {
        // This allocator is junk.
        if (p == reinterpret_cast<T*>(&data_[0]))
        {
            last_dealloc_size_ = n;
        }
    }

    std::size_t get_last_alloc_size() const
    {
        return last_alloc_size_;
    }

    std::size_t get_alloc_count() const
    {
        return alloc_count_;
    }

    std::size_t get_last_dealloc_size() const
    {
        return last_dealloc_size_;
    }

    operator array_constref_type() const
    {
        return data_;
    }

private:
    T           data_[SizeCount];
    std::size_t alloc_count_;
    std::size_t last_alloc_size_;
    std::size_t last_dealloc_size_;
};

// +----------------------------------------------------------------------+
/**
 * Test suite for running multiple allocators against the variable length array type.
 */
template <typename T>
class VLATestsGeneric : public ::testing::Test
{
};

namespace
{
static constexpr std::size_t VLATestsGeneric_MinMaxSize = 32;
static constexpr std::size_t VLATestsGeneric_O1HeapSize = O1HEAP_ALIGNMENT << 5;

static_assert(VLATestsGeneric_O1HeapSize > VLATestsGeneric_MinMaxSize, "Unexpected test environment encountered.");

}  // end anonymous namespace

using VLATestsGenericAllocators = ::testing::Types<nunavut::support::MallocAllocator<int>,
                                                   std::allocator<int>,
                                                   std::allocator<long long>,
                                                   O1HeapAllocator<int, VLATestsGeneric_O1HeapSize>,
                                                   JunkyStaticAllocator<int, VLATestsGeneric_MinMaxSize>>;
TYPED_TEST_SUITE(VLATestsGeneric, VLATestsGenericAllocators, );

TYPED_TEST(VLATestsGeneric, TestReserve)
{
    static_assert(10 < VLATestsGeneric_MinMaxSize,
                  "Test requires max size of array is less than max size of the smallest allocator");
    nunavut::support::VariableLengthArray<typename TypeParam::value_type, 10, TypeParam> subject;
    ASSERT_EQ(0U, subject.capacity());
    ASSERT_EQ(0U, subject.size());
    ASSERT_EQ(10U, subject.max_size());

    ASSERT_EQ(1U, subject.reserve(1));

    ASSERT_EQ(1U, subject.capacity());
    ASSERT_EQ(0U, subject.size());
    ASSERT_EQ(10U, subject.max_size());
}

TYPED_TEST(VLATestsGeneric, TestPush)
{
    nunavut::support::VariableLengthArray<typename TypeParam::value_type, VLATestsGeneric_MinMaxSize, TypeParam>
        subject;
    ASSERT_EQ(nullptr, subject.data());
    ASSERT_EQ(0U, subject.size());

    typename TypeParam::value_type x = 0;
    for (std::size_t i = 0; i < VLATestsGeneric_MinMaxSize; ++i)
    {
        subject.push_back(x);

        ASSERT_EQ(i + 1, subject.size());
        ASSERT_LE(subject.size(), subject.capacity());

        const typename TypeParam::value_type* const pushed = &subject[i];

        ASSERT_EQ(*pushed, x);
        ++x;
    }
}

TYPED_TEST(VLATestsGeneric, TestPop)
{
    static_assert(20 < VLATestsGeneric_MinMaxSize,
                  "Test requires max size of array is less than max size of the smallest allocator");
    nunavut::support::VariableLengthArray<typename TypeParam::value_type, 20, TypeParam> subject;
    ASSERT_EQ(10U, subject.reserve(10));
    subject.push_back(1);
    ASSERT_EQ(1U, subject.size());
    const typename TypeParam::value_type* const pushed = &subject[0];
    ASSERT_NE(nullptr, pushed);
    ASSERT_EQ(*pushed, 1);
    ASSERT_EQ(1U, subject.size());
    subject.pop_back();
    ASSERT_EQ(0U, subject.size());
    ASSERT_EQ(10U, subject.capacity());
}

TYPED_TEST(VLATestsGeneric, TestShrink)
{
    static_assert(20 < VLATestsGeneric_MinMaxSize,
                  "Test requires max size of array is less than max size of the smallest allocator");
    nunavut::support::VariableLengthArray<typename TypeParam::value_type, 20, TypeParam> subject;
    ASSERT_EQ(10U, subject.reserve(10));
    subject.push_back(1);
    ASSERT_EQ(1U, subject.size());
    const typename TypeParam::value_type* const pushed = &subject[0];
    ASSERT_NE(nullptr, pushed);
    ASSERT_EQ(*pushed, 1);
    ASSERT_EQ(1U, subject.size());
    ASSERT_EQ(10U, subject.capacity());
    subject.shrink_to_fit();
    ASSERT_EQ(1U, subject.capacity());
}

// +----------------------------------------------------------------------+
/**
 * Test suite for running static allocators against the variable length array type.
 */
template <typename T>
class VLATestsStatic : public ::testing::Test
{
};

using VLATestsStaticAllocators =
    ::testing::Types<O1HeapAllocator<int, O1HEAP_ALIGNMENT * 8>, JunkyStaticAllocator<int, 10>>;
TYPED_TEST_SUITE(VLATestsStatic, VLATestsStaticAllocators, );

TYPED_TEST(VLATestsStatic, TestOutOfMemory)
{
    nunavut::support::
        VariableLengthArray<typename TypeParam::value_type, std::numeric_limits<std::size_t>::max(), TypeParam>
            subject;
    ASSERT_EQ(0U, subject.capacity());

    bool        did_run_out_of_memory = false;
    std::size_t ran_out_of_memory_at  = 0;
    for (std::size_t i = 1; i <= 1024; ++i)
    {
        ASSERT_EQ(i - 1, subject.size());
        if (subject.reserve(i) < i)
        {
            did_run_out_of_memory = true;
            ran_out_of_memory_at  = i;
            break;
        }
        ASSERT_EQ(i, subject.capacity());
        subject.push_back(static_cast<typename TypeParam::value_type>(i));
        ASSERT_EQ(i, subject.size());
        typename TypeParam::value_type* pushed = &subject[i - 1];
        ASSERT_NE(nullptr, pushed);
        ASSERT_EQ(static_cast<typename TypeParam::value_type>(i), *pushed);
    }
    ASSERT_TRUE(did_run_out_of_memory);
    const std::size_t size_before = subject.size();
    try
    {
        subject.push_back(0);
    } catch (const std::length_error& e)
    {
        std::cerr << e.what() << '\n';
    } catch (const std::bad_alloc& e)
    {
        std::cerr << e.what() << '\n';
    }

    ASSERT_EQ(size_before, subject.size());
    for (std::size_t i = 1; i < ran_out_of_memory_at; ++i)
    {
        ASSERT_EQ(static_cast<typename TypeParam::value_type>(i), subject[i - 1]);
    }
}

TYPED_TEST(VLATestsStatic, TestOverMaxSize)
{
    static constexpr std::size_t MaxSize = 5;
    static_assert(MaxSize > 0, "Test assumes MaxSize > 0");
    nunavut::support::VariableLengthArray<typename TypeParam::value_type, MaxSize, TypeParam> subject;
    ASSERT_EQ(0U, subject.capacity());

    for (std::size_t i = 1; i <= MaxSize; ++i)
    {
        ASSERT_EQ(i, subject.reserve(i));
        subject.push_back(static_cast<typename TypeParam::value_type>(i));
        typename TypeParam::value_type* pushed = &subject[i - 1];
        ASSERT_EQ(i, subject.size());
        ASSERT_NE(nullptr, pushed);
        ASSERT_EQ(static_cast<typename TypeParam::value_type>(i), *pushed);
    }
    ASSERT_EQ(MaxSize, subject.reserve(MaxSize + 1));

    ASSERT_EQ(MaxSize, subject.size());
    try
    {
        subject.push_back(0);
    } catch (const std::length_error& e)
    {
        std::cerr << e.what() << '\n';
    } catch (const std::bad_alloc& e)
    {
        std::cerr << e.what() << '\n';
    }

    ASSERT_EQ(MaxSize, subject.size());
    for (std::size_t i = 0; i < MaxSize; ++i)
    {
        ASSERT_EQ(static_cast<typename TypeParam::value_type>(i + 1), subject[i]);
    }
}

// +----------------------------------------------------------------------+
/**
 * Test suite to ensure non-trivial objects are properly handled.
 */

TEST(VLATestsNonTrivial, TestDeallocSize)
{
    nunavut::support::VariableLengthArray<int, 10, JunkyStaticAllocator<int, 10>> subject;
    ASSERT_EQ(0U, subject.get_allocator().get_alloc_count());
    subject.reserve(10);
    ASSERT_EQ(1U, subject.get_allocator().get_alloc_count());
    ASSERT_EQ(10U, subject.get_allocator().get_last_alloc_size());
    ASSERT_EQ(0U, subject.get_allocator().get_last_dealloc_size());
    subject.pop_back();
    subject.shrink_to_fit();
    ASSERT_EQ(10U, subject.get_allocator().get_last_dealloc_size());
}

TEST(VLATestsNonTrivial, TestDestroy)
{
    int dtor_called = 0;

    auto subject = std::make_shared<nunavut::support::VariableLengthArray<Doomed, 10, std::allocator<Doomed>>>();

    ASSERT_EQ(10U, subject->reserve(10));
    subject->push_back(Doomed(&dtor_called));
    ASSERT_EQ(1U, subject->size());
    subject->push_back(Doomed(&dtor_called));
    ASSERT_EQ(2U, subject->size());
    ASSERT_EQ(0, dtor_called);
    subject.reset();
    ASSERT_EQ(2, dtor_called);
}

TEST(VLATestsNonTrivial, TestNonFunamental)
{
    int dtor_called = 0;

    nunavut::support::VariableLengthArray<Doomed, 10, std::allocator<Doomed>> subject;
    ASSERT_EQ(10U, subject.reserve(10));
    subject.push_back(Doomed(&dtor_called));
    ASSERT_EQ(1U, subject.size());
    subject.pop_back();
    ASSERT_EQ(1, dtor_called);
}

TEST(VLATestsNonTrivial, TestNotMovable)
{
    class NotMovable
    {
    public:
        NotMovable() {}
        NotMovable(NotMovable&&) = delete;
        NotMovable(const NotMovable& rhs) noexcept
        {
            (void) rhs;
        }
    };
    nunavut::support::VariableLengthArray<NotMovable, 10, std::allocator<NotMovable>> subject;
    ASSERT_EQ(10U, subject.reserve(10));
    NotMovable source;
    subject.push_back(source);
    ASSERT_EQ(1U, subject.size());
}

TEST(VLATestsNonTrivial, TestMovable)
{
    class Movable
    {
    public:
        Movable(int data)
            : data_(data)
        {
        }
        Movable(const Movable&) = delete;
        Movable(Movable&& move_from) noexcept
            : data_(move_from.data_)
        {
            move_from.data_ = 0;
        }
        int get_data() const
        {
            return data_;
        }

    private:
        int data_;
    };
    nunavut::support::VariableLengthArray<Movable, 10, std::allocator<Movable>> subject;
    ASSERT_EQ(10U, subject.reserve(10));
    subject.push_back(Movable(1));
    ASSERT_EQ(1U, subject.size());
    Movable* pushed = &subject[0];
    ASSERT_NE(nullptr, pushed);
    ASSERT_EQ(1, pushed->get_data());
}

TEST(VLATestsNonTrivial, TestMoveToVector)
{
    nunavut::support::VariableLengthArray<std::size_t, 10, std::allocator<std::size_t>> subject;
    ASSERT_EQ(decltype(subject)::type_max_size, subject.reserve(decltype(subject)::type_max_size));
    for (std::size_t i = 0; i < decltype(subject)::type_max_size; ++i)
    {
        subject.push_back(i);
        ASSERT_EQ(i + 1, subject.size());
    }
    std::vector<std::size_t> a(subject.cbegin(), subject.cend());
    for (std::size_t i = 0; i < decltype(subject)::type_max_size; ++i)
    {
        ASSERT_EQ(i, a[i]);
    }
}

TEST(VLATestsNonTrivial, TestInitializerArray)
{
    nunavut::support::VariableLengthArray<std::size_t, 10> subject{{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}};
    ASSERT_EQ(10U, subject.size());
    for (std::size_t i = 0; i < subject.size(); ++i)
    {
        ASSERT_EQ(subject.size() - i, subject[i]);
    }
}

TEST(VLATestsNonTrivial, TestCopyContructor)
{
    nunavut::support::VariableLengthArray<std::size_t, 10> fixture{{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}};
    nunavut::support::VariableLengthArray<std::size_t, 10> subject(fixture);
    ASSERT_EQ(10U, subject.size());
    for (std::size_t i = 0; i < subject.size(); ++i)
    {
        ASSERT_EQ(subject.size() - i, subject[i]);
    }
}

TEST(VLATestsNonTrivial, TestMoveContructor)
{
    nunavut::support::VariableLengthArray<std::size_t, 10> fixture{{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}};
    nunavut::support::VariableLengthArray<std::size_t, 10> subject(std::move(fixture));
    ASSERT_EQ(10U, subject.size());
    for (std::size_t i = 0; i < subject.size(); ++i)
    {
        ASSERT_EQ(subject.size() - i, subject[i]);
    }
    ASSERT_EQ(0U, fixture.size());
    ASSERT_EQ(0U, fixture.capacity());
}

TEST(VLATestsNonTrivial, TestCompare)
{
    nunavut::support::VariableLengthArray<std::size_t, 10> one{{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}};
    nunavut::support::VariableLengthArray<std::size_t, 10> two{{10, 9, 8, 7, 6, 5, 4, 3, 2, 1}};
    nunavut::support::VariableLengthArray<std::size_t, 10> three{{9, 8, 7, 6, 5, 4, 3, 2, 1}};
    ASSERT_EQ(one, one);
    ASSERT_EQ(one, two);
    ASSERT_NE(one, three);
}

TEST(VLATestsNonTrivial, TestFPCompare)
{
    nunavut::support::VariableLengthArray<double, 10> one{{1.00, 2.00}};
    nunavut::support::VariableLengthArray<double, 10> two{{1.00, 2.00}};
    const double epsilon_for_two_comparison = std::nextafter(4.00, INFINITY) - 4.00;
    nunavut::support::VariableLengthArray<double, 10> three{
        {1.00, std::nextafter(2.00 + epsilon_for_two_comparison, INFINITY)}};
    ASSERT_EQ(one, one);
    ASSERT_EQ(one, two);
    ASSERT_NE(one, three);
}

TEST(VLATestsNonTrivial, TestCopyAssignment)
{
    nunavut::support::VariableLengthArray<double, 2> lhs{1.00};
    nunavut::support::VariableLengthArray<double, 2> rhs{{2.00, 3.00}};
    ASSERT_EQ(1U, lhs.size());
    ASSERT_EQ(2U, rhs.size());
    ASSERT_NE(lhs, rhs);
    lhs = rhs;
    ASSERT_EQ(2U, lhs.size());
    ASSERT_EQ(2U, rhs.size());
    ASSERT_EQ(lhs, rhs);
}

TEST(VLATestsNonTrivial, TestMoveAssignment)
{
    nunavut::support::VariableLengthArray<std::string, 3> lhs{{std::string("one"), std::string("two")}};
    nunavut::support::VariableLengthArray<std::string, 3> rhs{
        {std::string("three"), std::string("four"), std::string("five")}};
    ASSERT_EQ(2U, lhs.size());
    ASSERT_EQ(3U, rhs.size());
    ASSERT_NE(lhs, rhs);
    lhs = std::move(rhs);
    ASSERT_EQ(3U, lhs.size());
    ASSERT_EQ(0U, rhs.size());
    ASSERT_EQ(0U, rhs.capacity());
    ASSERT_NE(lhs, rhs);
    ASSERT_EQ(std::string("three"), lhs[0]);
}

TEST(VLATestsNonTrivial, TestPushBackGrowsCapacity)
{
    static constexpr std::size_t                        MaxSize = 5;
    nunavut::support::VariableLengthArray<int, MaxSize> subject;
    ASSERT_EQ(0U, subject.capacity());
    subject.push_back();
    ASSERT_LE(1U, subject.capacity());
}
