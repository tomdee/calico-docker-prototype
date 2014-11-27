FROM ubuntu:14.04

RUN apt-get update
RUN apt-get install -y python-zmq

RUN mkdir /opt/plugin
RUN mkdir /opt/scripts
ADD plugin.py /opt/scripts/
