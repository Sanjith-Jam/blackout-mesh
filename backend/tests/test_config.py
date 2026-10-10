import pytest
from app.core.config import SiteProfile, Asset, AssetType

def test_duplicate_ids():
    with pytest.raises(ValueError, match="Duplicate Asset ID"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="A", type=AssetType.SOURCE, name="S1"),
                Asset(id="A", type=AssetType.FEEDER, name="F1", parent_id="A")
            ]
        )

def test_dangling_parent():
    with pytest.raises(ValueError, match="Dangling parent_id: INVALID"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="S1", type=AssetType.SOURCE, name="S1"),
                Asset(id="F1", type=AssetType.FEEDER, name="F1", parent_id="INVALID")
            ]
        )

def test_cycle():
    with pytest.raises(ValueError, match="Cycle detected"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="A", type=AssetType.FEEDER, name="A", parent_id="B"),
                Asset(id="B", type=AssetType.FEEDER, name="B", parent_id="A")
            ]
        )

def test_capacity_exceeded():
    with pytest.raises(ValueError, match="Asset S1 capacity 100 exceeded by children total 150"):
        SiteProfile(
            version="1.0",
            name="Test",
            assets=[
                Asset(id="S1", type=AssetType.SOURCE, name="S1", capacity_w=100),
                Asset(id="F1", type=AssetType.FEEDER, name="F1", parent_id="S1", capacity_w=75),
                Asset(id="F2", type=AssetType.FEEDER, name="F2", parent_id="S1", capacity_w=75)
            ]
        )
