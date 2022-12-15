import hashlib
import subprocess

import requests


class DocumentSigningTimeStampService:
    TIMESTAMP_SERVER = "http://timestamp.entrust.net/TSS/RFC3161sha2TS"
    DEFAULT_HASH = "sha256"
    CERT_FILE = "entrust_2048_ca.cer"
    REQUEST_FILE = "request.tsq"
    RESPONSE_FILE = "response.tsr"

    def create_timestamp(self, data: bytes):
        """Creates a hash of the incomming data and sends it to the timestamp server.
        The timestamp server will add a timestamp to the data, and then sign it with its
        private key. The signed response is returned.

        Args:
            data (bytes): The data that should be timestamped.

        Returns:
            _type_: _description_
        """

        digest = self._create_digest(data)
        query = (
            f"openssl ts -query -digest {digest} -cert -{self.DEFAULT_HASH} -no_nonce"
        )
        result = subprocess.check_output(query, shell=True)
        return self._sign_data(request=result)

    def _create_digest(self, data: bytes) -> str:
        """Create a digest of the data."""

        m = hashlib.new(self.DEFAULT_HASH)
        m.update(data)
        return m.hexdigest()

    def _sign_data(self, request: bytes) -> bytes:
        """Send the request to the timestamp server and return the signed response."""

        res = requests.post(
            self.TIMESTAMP_SERVER,
            data=request,
            headers={"Content-Type": "application/timestamp-query"},
        )
        res.raise_for_status()

        return res.content

    def verify_request(self, verify_against, signed_response):
        """Verify the signed response against the original data.

        Args:
            verify_against (bytes): The original data that was timestamped, and signed.
                This data will be checked against the corresponding public key of the timestamp
                server.
            signed_response (bytes): The signed response from the timestamp server. This is the
                hash of the original data, and the timestamp. The timestamp server will have signed
                this data with its private key.
        """

        x = self.create_timestamp(verify_against)
        with open(self.REQUEST_FILE, "wb") as f:
            f.write(x)

        with open(self.RESPONSE_FILE, "wb") as f:
            f.write(signed_response)

        verify = f"openssl ts -verify -in {self.RESPONSE_FILE} -queryfile {self.REQUEST_FILE} -CAfile {self.CERT_FILE}"
        result = subprocess.check_output(verify, shell=True)
        return "verification: ok" in result.decode("utf-8").strip().lower()
