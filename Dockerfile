FROM python:3.11-bullseye

LABEL "com.github.actions.name"="LLM Reviewer"
LABEL "com.github.actions.description"="Automated pull requests reviewing and issues triaging with an LLM"

WORKDIR /app

COPY ./app /app

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

ENTRYPOINT [ "/app/main.py" ]
