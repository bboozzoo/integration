Mender: Integration
==============================================

Mender is an open source over-the-air (OTA) software updater for embedded Linux
devices. Mender comprises a client running at the embedded device, as well as a
server that manages deployments across many devices.

This repository contains a Docker-based environment allowing to run all Mender
backend services as a single system. Each service has a dedicated Dockerhub
repository, where tagged Docker builds are stored. Images are pulled and started
in a coordinated fashion via `docker-compose` and the associated
`docker-compose.yml` file.

Requirements:

* docker-engine 1.10
* docker-compose 1.7


![Mender logo](https://mender.io/user/pages/04.resources/_logos/logoS.png)


## Getting started

To start using Mender, we recommend that you begin with the Getting started
section in [the Mender documentation](https://docs.mender.io/).


## Services

The integration environment brings together the following services:

- [Mender Device Admission Service](https://github.com/mendersoftware/deviceadm)
- [Mender Device Authentication Service](https://github.com/mendersoftware/deviceauth)
- [Mender Deployment Service](https://github.com/mendersoftware/deployments)
- [Mender Device Inventory Service](https://github.com/mendersoftware/inventory)
- [Mender User Administration Service](https://github.com/mendersoftware/useradm)
- [Mender API Gateway](https://github.com/mendersoftware/mender-api-gateway-docker)
- [Minio](https://www.minio.io/) object storage
- Storage service proxy based on [OpenResty](https://openresty.org/en/)

## How to use in production

A provided `docker-compose.yml` file will provision the following set of
services:

```
        |
        |                                            +-------------------------+
        |                                            |                         |
        |                                       +--->|  Device Authentication  |
        |                                       |    |  (mender-device-auth)   |
        |                                       |    +-------------------------+
        |        +-----------------------+      |    |                         |
   port |        |                       |      +--->|  Device Admission       |
   8080 | <----> |  API Gateway          |      |    |  (mender-device-adm)    |
        |        |  (mender-api-gateway) |<-----+    +-------------------------+
        |        +-----------------------+      |    |                         |
        |                                       +--->|  Inventory              |
        |                                       |    |  (mender-inventory)     |
        |                                       |    +-------------------------+
        |                                       |    |                         |
        |                                       +--->|  User Administration    |
        |                                       |    |  (mender-useradm)       |
        |                                       |    +-------------------------+
        |                                       +--->|                         |
        |                                            |  Deployments            |
        |              +---------------------------->|  (mender-deployments)   |
        |              |                             +-------------------------+
        |              |
        |              |
        |              v
        |        +------------------+                 +---------+
   port |        |                  |                 |         |
   9000 | <----> |  Storage Proxy   |<--------------->| Minio   |
        |        |  (storage-proxy) |                 | (minio) |
        |        +------------------+                 +---------+
        |
```

It is customary to provide deployment specific overrides in a separate compose
file. This can either be `docker-compose.override.yml` file (detected and
included automatically by `docker-compose` command) or a separate file. If a
separate file is used, it needs to be explicitly included in command line when
running `docker-compose` like this:

```
docker-compose -f docker-compose.yml -f my-other-file.yml up
```

Mender artifacts file are served from storage backend provided by Minio object
storage in the reference setup.

### API Gateway certificate

API Gateway certificate needs to be mounted into the gateway's container. This
can be achieved using a compose file with the following entry:

```
    mender-api-gateway:
        volumes:
            - ./ssl/mender-api-gateway/cert.pem:/var/www/mendersoftware/cert/cert.pem
            - ./ssl/mender-api-gateway/key.pem:/var/www/mendersoftware/cert/key.pem

```

Where certificate and key paths need to be replaced with paths to your
certificate and key files.

### Token signing keys

Mender backend uses JWT tokens for device and user authentication. The tokens
are cryptographically signed and their authenticity is verified when making
requests to the backend. Tokens are handed out
by [Device Authentication](https://github.com/mendersoftware/deviceauth)
and [User Administration](https://github.com/mendersoftware/useradm) services.

Before starting mender in production, one needs to provide RSA private keys in
PEM format for both services. This can be accomplished by generating key using
openssl:

```
openssl genpkey -algorithm RSA -out key.pem -pkeyopt rsa_keygen_bits:2048
```

and mounting the keys into respective containers by adding the following entry
to compose file (replacing local key paths with paths of your own):

```
    mender-useradm:
        volumes:
            - ./keys/useradm-private.pem:/etc/useradm/rsa/private.pem

    mender-device-auth:
        volumes:
            - ./keys/deviceauth-private.pem:/etc/deviceauth/rsa/private.pem
```

It is recommended to use separate keys for `mender-useradm` and
`mender-device-auth` services.

### Artifact Storage

Mender artifacts are kept by default in S3-like object store provided by Minio.
It is possible to use the actual Amazon S3 service for storage as well. See
section [S3 storage backend](#s3-storage-backend) for details.

#### Storage Proxy

Storage proxy is responsible for wrapping Minio object storage API with HTTPS
and provides knobs for implementing bandwidth and connection throttling.

The proxy is implemented as a nginx service (based on OpenResty image), with
configuration provided in `storage-proxy/nginx.conf` file.

##### Storage Proxy certificate

Storage proxy certificate needs to be mounted into the container. This can be
implemented using a `docker-compose` file with the following entry:

```
    storage-proxy:
        volumes:
            - ./ssl/storage-proxy/s3.docker.mender.io.crt:/var/www/storage-proxy/cert/cert.crt
            - ./ssl/storage-proxy/s3.docker.mender.io.key:/var/www/storage-proxy/cert/key.pem
```

Replace path to demo certificate and key with paths to your certificate and key.

Deployments service communicates with Minio object storage via storage proxy.
For this reason, `mender-deployments` service must be provisioned with a
certificate of a storage proxy for host verification purpose. This can be
implemented by adding the following entry to compose file:

```
    mender-deployments:
        volumes:
            - ./ssl/storage-proxy/s3.docker.mender.io.crt:/etc/ssl/certs/s3.docker.mender.io.crt
        environment:
            - STORAGE_BACKEND_CERT=/etc/ssl/certs/s3.docker.mender.io.crt
```

`STORAGE_BACKEND_CERT` defines a path to the certificate of storage proxy within
the container's filesystem. Deployments service will automatically load the
certificate into its trust store.

##### Bandwidth and connection limiting

`storage-proxy` container is aware of 2 environment variables:

* `MAX_CONNECTIONS` - limits the number of concurrent GET requests. Integer,
  defaults to 100.

* `DOWNLOAD_SPEED` - limits the download speed of proxy response. String,
  defaults to `1m` (1MByte/s). Detailed format description is provided in nginx
  documentation
  of
  [limit_rate](https://nginx.org/en/docs/http/ngx_http_core_module.html#limit_rate) variable

These options can be adjusted using a separate compose file with the following
entry (example limiting download speed to 512kB/s, max 5 concurrent transfers):

```
    storage-proxy:
        environment:
            MAX_CONNECTIONS: 5
            DOWNLOAD_SPEED: 512k
```

#### S3 storage backend

It is possible to use S3 as a storage backend in place of Minio object storage.
This can be achieved using a separate compose file with the following entry:

```
    mender-deployments:
        environment:
            AWS_ACCESS_KEY_ID: <your-aws-access-key-id>
            AWS_SECRET_ACCESS_KEY: <your-aws-secret-access-key>
            AWS_URI: https://s3.amazonaws.com
```


## Integrating a new service

Adding a new service to the setup involves:

* creating a dedicated Dockerfile
* setting up a Dockerhub repository and a CI build pipeline
* adding the service's config under `docker-compose.yml`

Guidelines and things to consider:

* assign the service a name that is unique within `docker-compose.yml`
* add the service to the `mender` network
* setup the correct routing and authentication for the new service in the
[Mender API Gateway](https://github.com/mendersoftware/mender-api-gateway-docker)
* extend the common service `mender-common/common.yml`

## How to use in development

Running the integration setup brings up a complete system of services; as such
it can readily be used for testing, staging or demo environments.

In development scenarios however some additional strategies apply, described in
the following sections.

### Developing a new service

The default approach to integrating a service, involving the full build
pipeline, is not conducive to quick develop/build/test cycles. Therefore, when
prototyping a new service against an existing system, it can be useful to:

* create a dedicated Dockerfile for your service and build it locally:
```
cd FOLDER_WITH_DOCKERFILE
docker build -t MY_DOCKER_TAG  .
```

* include the service as usual in `docker-compose.yml`, paying attention to the
  image tag you just created:

```
    #
    # myservice
    #
    myservice:
        image: MY_DOCKER_TAG
```

* add any number of [volumes](https://docs.docker.com/compose/compose-file/#/volumes-volume-driver)
to your service, to mount your local binaries and config files into the Docker
container, e.g.:

```
    myservice:
        ...
        volumes:
             /some/localhost/folder/myconfig.yaml:/usr/bin/myconfig.yaml
             /some/localhost/folder/mybinary:/usr/bin/mybinary
            ...
```

When you run the setup, your new service will be a part of it; also, it will be
running binaries from your local machine, which means you can quickly recompile
them and restart `integration` for changes to take effect.

Note that the correct routing and auth still have to be set up in the Mender API Gateway for the service
to be accessible from the outside. To experiment with new configuration:

* copy the [Gateway's main config file](https://github.com/mendersoftware/mender-api-gateway-docker/blob/master/nginx.conf)
locally

* in `docker-compose.yml`, again mount your local version inside the Gateway container:

```
    #
    # mender-api-gateway
    #
    mender-api-gateway:
        ...
        /some/localhost/folder/nginx.conf:/usr/local/openresty/nginx/conf/nginx.conf
```
Your changes will take effect when you restart the whole setup.

### Troubleshooting/developing an existing service

For troubleshooting and debugging, a similar approach involving Docker `volumes`
can be used. Assuming that a given service's image has been pulled to your local
machine, mount your local binaries and config files via `docker-compose.yml`:

```
    service:
        ...
        volumes:
             /some/localhost/folder/myconfig.yaml:/usr/bin/config.yaml
             /some/localhost/folder/mybinary:/usr/bin/service-binary
            ...
```

To obtain the locations of both binaries and config files, refer the service's
dedicated Dcokerfile.

Again, recompiling your local binary and restarting `integration` will make your
changes take effect. Note that the correct API Gateway config is probably
already set up for an existing service; if not, refer the previous section on
how to modify it.

### Enabling non-SSL access

For debugging purposes, it may be useful to temporarily enable non-SSL access.
API Gateway configuration enables plain HTTP on port 80, however the port is not
published by default, thus it remains inaccessible from the outside. For
convenience, an overlay compose file is provided that publishes port 80 of API
Gateway to port 8090 on current host. The overlay file has to be explicitly
included when setting up the environment like this:

```
docker-compose ... -f docker-compose.no-ssl.yml ...
```

**NOTE** make sure that plain HTTP port is not published in production
deployment.

## Demo client

The setup comes with a predefined client service (mender-client) that runs a
qemu VM in a container. The client will connect to the backend by accessing
`docker.mender.io` host (an alias assigned to `mender-api-gateway` service). The
client container will not be started by default and needs to be included
explicitly when running docker compose by listing multiple compose files as
described in [compose manual](https://docs.docker.com/compose/extends/#/multiple-compose-files).

To start the backend and a demo client run the following command:

```
docker-compose -f docker-compose.yml -f docker-compose.client.yml up
```

## Contributing

We welcome and ask for your contribution. If you would like to contribute to
Mender, please read our guide on how to best get started
[contributing code or documentation](https://github.com/mendersoftware/mender/blob/master/CONTRIBUTING.md).

## License

Mender is licensed under the Apache License, Version 2.0. See
[LICENSE](https://github.com/mendersoftware/integration/blob/master/LICENSE) for the
full license text.

## Security disclosure

We take security very seriously. If you come across any issue regarding
security, please disclose the information by sending an email to
[security@mender.io](security@mender.io). Please do not create a new public
issue. We thank you in advance for your cooperation.

## Connect with us

* Join our [Google
  group](https://groups.google.com/a/lists.mender.io/forum/#!forum/mender)
* Follow us on [Twitter](https://twitter.com/mender_io?target=_blank). Please
  feel free to tweet us questions.
* Fork us on [Github](https://github.com/mendersoftware)
* Email us at [contact@mender.io](mailto:contact@mender.io)
