"""Run the identity-only ASGI factory on the Cloud Run ingress port."""

import os

import uvicorn


def main():
    os.umask(0o077)
    uvicorn.run(
        "invitations.staging.app:from_env",
        factory=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
