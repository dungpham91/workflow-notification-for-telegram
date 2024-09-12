FROM python:3.12-slim

WORKDIR /app
COPY src/ .

RUN python -m pip install --upgrade pip && pip install requests PyGithub

CMD ["python", "main.py"]
