"""Datatype used when fetching from Github."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, Field, HttpUrl, RootModel


class SimpleUser(BaseModel):
    """A GitHub user."""

    name: str | None = None
    email: str | None = None
    login: str
    id: int
    node_id: str
    avatar_url: HttpUrl
    gravatar_id: str | None = None
    url: HttpUrl
    html_url: HttpUrl
    followers_url: HttpUrl
    following_url: str
    gists_url: str
    starred_url: str
    subscriptions_url: HttpUrl
    organizations_url: HttpUrl
    repos_url: HttpUrl
    events_url: str
    received_events_url: HttpUrl
    type: str
    site_admin: bool
    starred_at: str | None = None
    user_view_type: str | None = None


class ReleaseAsset(BaseModel):
    """Data related to a release."""

    url: HttpUrl
    browser_download_url: HttpUrl
    id: int
    node_id: str
    name: str = Field(..., description="The file name of the asset.")
    label: str | None = None
    state: str = Field(..., description="State of the release asset.")
    content_type: str
    size: int
    digest: str | None = None
    download_count: int
    created_at: datetime
    updated_at: datetime
    uploader: SimpleUser | None = None


class ReactionRollup(BaseModel, populate_by_name=True):
    """Represents reaction on a release."""

    url: HttpUrl
    total_count: int
    plus_one: int = Field(..., alias="+1")
    minus_one: int = Field(..., alias="-1")
    laugh: int
    confused: int
    heart: int
    hooray: int
    eyes: int
    rocket: int


class Release(BaseModel):
    """Represents an instance of Github release."""

    url: HttpUrl
    html_url: HttpUrl
    assets_url: HttpUrl
    upload_url: str
    tarball_url: HttpUrl | None = None
    zipball_url: HttpUrl | None = None
    id: int
    node_id: str
    tag_name: str = Field(..., description="The name of the tag.")
    target_commitish: str = Field(
        ...,
        description="Specifies the commitish value that determines where the Git tag is created from.",
    )
    name: str | None = None
    body: str | None = None
    draft: bool = Field(..., description="true to create a draft (unpublished) release, false to create a published one.")
    prerelease: bool = Field(..., description="Whether to identify the release as a prerelease or a full release.")
    immutable: bool | None = Field(default=None, description="Whether or not the release is immutable.")
    created_at: datetime
    published_at: datetime | None = None
    updated_at: datetime | None = None
    author: SimpleUser
    assets: list[ReleaseAsset]
    body_html: str | None = None
    body_text: str | None = None
    mentions_count: int | None = None
    discussion_url: HttpUrl | None = Field(default=None, description="The URL of the release discussion.")
    reactions: ReactionRollup | None = None


class ReleaseList(RootModel[list[Release]]):
    """Wrapper for the array response of GET /repos/{owner}/{repo}/releases."""
