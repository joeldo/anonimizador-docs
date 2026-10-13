import socket

import pytest

pytestmark = pytest.mark.usefixtures("sem_rede")


@pytest.mark.parametrize("address", [("127.0.0.1", 8000), ("203.0.113.1", 443)])
def test_bloqueia_inclusive_endpoints_locais(address: tuple[str, int]) -> None:
    with socket.socket() as sock:
        with pytest.raises(AssertionError, match="nao permite acesso a rede"):
            sock.connect(address)


def test_socketpair_interno_continua_funcionando() -> None:
    leitura, escrita = socket.socketpair()
    with leitura, escrita:
        escrita.sendall(b"teste")
        assert leitura.recv(5) == b"teste"
