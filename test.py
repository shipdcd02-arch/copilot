def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

if __name__ == "__main__":
    print("add(3, 4) =", add(3, 4))
    print("subtract(10, 3) =", subtract(10, 3))
    print("multiply(2, 5) =", multiply(2, 5))
    print("divide(10, 2) =", divide(10, 2))
