FROM ubuntu:14.04

RUN apt-get update
RUN apt-get install -y bird

ADD bird.conf /etc/bird/
ADD run_bird /usr/bin/
RUN chmod 777 /usr/bin/run_bird

RUN cp /etc/bird/bird.conf /etc/bird/bird1.conf
RUN cp /etc/bird/bird.conf /etc/bird/bird2.conf
RUN sed 's/LOCALADDR/10.240.254.171/' -if /etc/bird/bird1.conf
RUN sed 's/PEERADDR/10.240.58.221/' -if /etc/bird/bird1.conf
RUN sed 's/LOCALADDR/10.240.58.221/' -if /etc/bird/bird2.conf
RUN sed 's/PEERADDR/10.240.254.171/' -if /etc/bird/bird2.conf
