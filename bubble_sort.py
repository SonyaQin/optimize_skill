data = [12, 4, 56, 21, 43, 67]

def bubble_sort(arr):
    """Cocktail shaker sort - bidirectional bubble sort"""
    n = len(arr)
    start = 0
    end = n - 1
    swapped = True

    while swapped:
        swapped = False

        # Forward pass
        for j in range(start, end):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
                swapped = True

        if not swapped:
            break

        end -= 1
        swapped = False

        # Backward pass
        for j in range(end, start, -1):
            if arr[j-1] > arr[j]:
                arr[j-1], arr[j] = arr[j], arr[j-1]
                swapped = True

        start += 1

bubble_sort(data)
print(data)