from locust import HttpUser, task, between

class StudentUser(HttpUser):
    wait_time = between(1, 3)

    @task(2)
    def view_jobs(self):
        self.client.get("/jobs")

    @task(1)
    def view_landing(self):
        self.client.get("/")

    @task(1)
    def login(self):
        self.client.post("/login", {
            "email": "test@student.com",
            "password": "test123"
        })


class FirmaUser(HttpUser):
    wait_time = between(2, 4)

    @task
    def view_applications(self):
        self.client.get("/firma/applications")

    @task
    def login(self):
        self.client.post("/login", {
            "email": "firma@test.com",
            "password": "test123"
        })
