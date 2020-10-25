FROM python:3.7-slim

MAINTAINER barryzhan2017@gmail.com (modified by barry)

USER root

WORKDIR /app

ADD . /app

RUN pip install --trusted-host pypi.python.org -r requirements.txt

EXPOSE 80

ENV rds_host=user-service.ci3ta0leimzm.us-east-2.rds.amazonaws.com
ENV rds_user=admin
ENV rds_password=12345678

CMD ["python", "app.py"]