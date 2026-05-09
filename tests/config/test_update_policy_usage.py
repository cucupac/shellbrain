"""Update-policy config usage contracts for normalized gate loading."""

from app.startup.update_policy import get_update_policy_settings


def test_update_policy_should_expose_configured_gate_list(monkeypatch) -> None:
    """update policy should always expose its configured gate list."""

    monkeypatch.setattr(
        "app.startup.update_policy.get_config_provider",
        lambda: type(
            "_StubConfigProvider",
            (),
            {
                "get_update_policy": staticmethod(
                    lambda: {"gates": ["schema", "semantic", "integrity"]}
                )
            },
        )(),
    )

    assert get_update_policy_settings() == {
        "gates": ["schema", "semantic", "integrity"]
    }
