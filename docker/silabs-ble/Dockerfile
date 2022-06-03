FROM rail-dev:latest
# Create arguments to set the default local user information
ARG CONTAINER_USER=matran
ARG CONTAINER_UID=646887354

# Install all python packages we need for BLE
USER root
RUN pip install \
    pyyaml
RUN pip3 install \
    pyxb \
    html2text

USER ${CONTAINER_USER}
CMD ["/bin/bash"]
