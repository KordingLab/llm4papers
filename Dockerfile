# A Dockerfile to run the application polling service as a container
FROM python:3.11-slim-buster
RUN apt-get update && apt-get install -y git
RUN pip install poetry
WORKDIR /app
COPY . .
RUN poetry install
CMD ["poetry", "run", "python3", "llm4papers/service.py"]