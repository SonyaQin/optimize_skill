data = [12, 4, 56, 21, 43, 67]

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        swapped = False
        limit = n - i - 1  # Cache loop boundary
        for j in range(limit):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
                swapped = True
        if not swapped:
            break

bubble_sort(data)
print(data)