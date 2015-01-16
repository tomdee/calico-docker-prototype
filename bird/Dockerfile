FROM ubuntu:14.04

RUN apt-get update
RUN apt-get install -y bird

ADD bird.conf /etc/bird/
ADD run_bird /usr/bin/
RUN chmod 777 /usr/bin/run_bird
RUN mkdir /var/log/bird
