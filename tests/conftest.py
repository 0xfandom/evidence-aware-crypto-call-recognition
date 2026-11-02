import os

import pytest

from evidence_aware_crypto_call_recognition.contract import Author, Post, PostContext, PostKind


def make_post(text: str, *, source_id: str | None = "t-1", handle: str | None = "@tester",
              kind: PostKind = PostKind.ORIGINAL, parent: str | None = None, quoted: str | None = None) -> Post:
    return Post(
        source_id=source_id,
        author=Author(handle=handle, platform_user_id="42") if handle else None,
        text=text,
        context=PostContext(kind=kind, parent_text=parent, quoted_text=quoted),
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("EACR_LIVE") == "1":
        return
    skip_live = pytest.mark.skip(reason="live test: set EACR_LIVE=1 (calls Claude, costs money)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
