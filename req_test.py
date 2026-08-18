import threading
import requests
import time


class MyAPI:
    def __init__(self):
        pass

    def method1(self):
        # GET request to API endpoint
        response = requests.get("https://jsonplaceholder.typicode.com/todos/1")

        print(f"Method 1 response: {response.text}")

    def method2(self):
        # POST request to API endpoint
        data = {"title": "foo", "body": "bar", "userId": 1}
        response = requests.post("https://jsonplaceholder.typicode.com/posts",
                                 data=data)

        print(f"Method 2 response: {response.text}")

    def method3(self):
        # GET request to API endpoint
        response = requests.get(
            "https://jsonplaceholder.typicode.com/comments/1")

        print(f"Method 3 response: {response.text}")

    def method4(self):
        # POST request to API endpoint
        data = {
            "name": "John Doe",
            "email": "johndoe@example.com",
            "phone": "1234567890"
        }
        response = requests.post("https://jsonplaceholder.typicode.com/users",
                                 data=data)
        print(f"Method 4 response: {response.text}")


n1 = time.time()
print("Running........")
api = MyAPI()

api.method1()
api.method2()
api.method3()
api.method4()
n2 = time.time()
print("Without multi thread finishes at : :", round((n2 - n1), 2))

t1 = threading.Thread(target=api.method1)
t2 = threading.Thread(target=api.method2)
t3 = threading.Thread(target=api.method3)
t4 = threading.Thread(target=api.method4)

t1.start()
t2.start()
t3.start()
t4.start()

t1.join()
t2.join()
t3.join()
t4.join()
print("With multi thread finishes at : :", round(time.time() - n2, 2))
