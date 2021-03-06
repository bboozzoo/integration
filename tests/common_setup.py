#!/usr/bin/python
# Copyright 2016 Mender Software AS
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        https://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
import pytest

from MenderAPI import auth, adm
from common import *
from common_docker import *

@pytest.fixture(scope="function")
def standard_setup_one_client():
    if setup_type() == ST_OneClient:
        return

    restart_docker_compose()
    auth.reset_auth_token()

    set_setup_type(ST_OneClient)


def setup_set_client_number(clients):
    docker_compose_cmd("scale mender-client=%d" % clients)
    ssh_is_opened()

    set_setup_type(None)


@pytest.fixture(scope="function")
def standard_setup_one_client_bootstrapped():
    if setup_type() == ST_OneClientBootstrapped:
        return

    restart_docker_compose()
    auth.reset_auth_token()
    adm.accept_devices(1)

    set_setup_type(ST_OneClientBootstrapped)


@pytest.fixture(scope="function")
def standard_setup_two_clients_bootstrapped():
    if setup_type() == ST_TwoClientsBootstrapped:
        return

    restart_docker_compose()
    auth.reset_auth_token()
    setup_set_client_number(2)
    adm.accept_devices(2)

    set_setup_type(ST_TwoClientsBootstrapped)

@pytest.fixture(scope="function")
def standard_setup_one_client_bootstrapped_with_s3():
    if setup_type() == ST_OneClientsBootstrapped_AWS_S3:
        return

    stop_docker_compose()

    docker_compose_cmd("-f ../docker-compose.client.yml \
                        -f ../docker-compose.storage.s3.yml \
                        -f ../docker-compose.yml \
                        -f ../extra/travis-testing/s3.yml up -d",
                        use_common_files=False)

    docker_compose_cmd("logs -f &")
    ssh_is_opened()

    auth.reset_auth_token()
    adm.accept_devices(1)

    set_setup_type(ST_OneClientsBootstrapped_AWS_S3)
