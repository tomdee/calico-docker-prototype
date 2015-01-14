FROM ubuntu:14.04

RUN apt-get update
RUN apt-get install -y bird

ADD bird.conf /etc/bird/
ADD run_bird /usr/bin/
RUN chmod 777 /usr/bin/run_bird
RUN mkdir /var/log/bird

RUN cp /etc/bird/bird.conf /etc/bird/bird1.conf
RUN cp /etc/bird/bird.conf /etc/bird/bird2.conf
RUN sed 's/LOCALADDR/IP1/' -i /etc/bird/bird1.conf
RUN sed 's/PEERADDR/IP2/' -i /etc/bird/bird1.conf
RUN sed 's/LOCALADDR/IP2/' -i /etc/bird/bird2.conf
RUN sed 's/PEERADDR/IP1/' -i /etc/bird/bird2.conf
