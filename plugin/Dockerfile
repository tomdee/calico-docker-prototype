FROM ubuntu:14.04

RUN apt-get update
RUN apt-get install -y python-zmq

RUN mkdir /opt/plugin
ADD plugin.py . 
RUN chmod +x plugin.py

