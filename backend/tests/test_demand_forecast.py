from app.forecast import DemandForecast


def test_causal_forecast_warmup_shortage_and_staleness():
    now = [0]
    forecast = DemandForecast(clock=lambda: now[0])
    for value in [3900, 4100, 4400]:
        forecast.observe("run1", value)
        now[0] += 10
    assert forecast.predict(6000)["status"] == "UNKNOWN"
    forecast.observe("run1", 4750)
    result = forecast.predict(6000)
    assert result["status"] == "SHORTAGE_RISK"
    assert result["first_shortage_s"] <= 60
    assert len(result["points"]) == 6
    assert all(0 <= p["lower_w"] <= p["demand_w"] <= p["upper_w"] <= 14000 for p in result["points"])
    now[0] += 21
    assert forecast.predict(6000)["points"] == []
    forecast.observe("run1", 4800)
    assert len(forecast.samples) == 1


def test_reset_duplicate_invalid_and_shock_abstain():
    now = [0]
    forecast = DemandForecast(clock=lambda: now[0])
    forecast.observe("run1", 4000)
    forecast.observe("run1", 5000)
    assert list(forecast.samples) == [4000]
    for value in [4100, 4200, 10000]:
        now[0] += 10
        forecast.observe("run1", value)
    assert forecast.predict(6000)["status"] == "UNKNOWN"
    forecast.observe("run2", 4000)
    assert list(forecast.samples) == [4000]
    now[0] += 10
    forecast.observe("run2", float("nan"))
    assert not forecast.samples


def test_missing_artifact_and_replay_do_not_invent_live_data(tmp_path):
    forecast = DemandForecast(model_path=tmp_path / "missing.json")
    assert forecast.predict(6000)["status"] == "UNKNOWN"
    forecast = DemandForecast()
    replay = forecast.predict(6000, "SYNTHETIC_REPLAY", 3)
    assert replay["status"] == "SHORTAGE_RISK"
    assert not forecast.samples
    assert replay["sample_age_s"] is None
