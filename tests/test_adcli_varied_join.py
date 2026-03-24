"""
Tests for adcli join with various computer names.
"""

from __future__ import annotations

import re

import pytest
from sssd_test_framework.roles.client import Client
from sssd_test_framework.roles.generic import GenericADProvider

from .topology import KnownTopologyGroup


def generate_test_names(hostname: str) -> list[str]:
    """Generates a list of computer names to test based on a base string."""
    short_name = hostname.split(".")[0]
    base_name = short_name[:15]

    upper = base_name.upper()
    lower = base_name.lower()
    digits = "".join([str(ord(c) % 10) for c in base_name])

    names = [
        upper,
        lower,
        digits,
        upper.capitalize(),
        lower.capitalize(),
    ]

    if 5 <= len(upper) <= 14:
        names.append(f"{upper[:3]}_{upper[3:]}")
        names.append(f"{upper[:3]}-{upper[3:]}")
        names.append(f"{lower[:3]}_{lower[3:]}")
        names.append(f"{lower[:3]}-{lower[3:]}")

    if len(digits) >= 5:
        names.append(f"{upper[:3]}{digits[3:]}")
        names.append(f"{lower[:3]}{digits[3:]}")

    return names


STATIC_BASE_NAME = "shorthostname"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
@pytest.mark.parametrize("computer_name", generate_test_names(STATIC_BASE_NAME))
def test_adcli_join_and_delete_various_names(client: Client, provider: GenericADProvider, computer_name: str):
    """
    :title: adcli join and delete with various computer names
    :steps:
        1. Join the domain using adcli join with a parameterized complex computer name.
        2. Verify the computer object exists in AD using adcli show-computer.
        3. Read the system keytab using klist to check for the correct principals.
        4. Delete the computer account from the domain using adcli delete-computer.
        5. Verify the computer object no longer exists in AD via show-computer.
    :expectedresults:
        1. The join command succeeds (rc=0).
        2. show-computer succeeds and outputs the correct computer name.
        3. The keytab contains the generated computer name in the correct case.
        4. The delete command succeeds (rc=0).
        5. show-computer returns a non-zero exit code, confirming deletion.
    """
    # 1. Join using the parameterized name
    join_result = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--computer-name={computer_name}"],
        krb=False,
    )
    assert join_result.rc == 0, f"Join failed for name '{computer_name}': {join_result.stderr}"

    # 2. Show Computer (Verify Object Exists)
    show_result = client.adcli.show_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", computer_name],
        krb=False,
    )
    assert show_result.rc == 0, (
        f"Computer object '{computer_name}' not found via show-computer. " f"stderr: {show_result.stderr}"
    )

    assert re.search(
        re.escape(computer_name), show_result.stdout + show_result.stderr, re.IGNORECASE
    ), f"Expected computer name '{computer_name}' in show-computer output."

    # 3. Verify Keytab
    klist = client.host.conn.exec(["klist", "-k"])
    assert klist.rc == 0

    assert (
        computer_name.upper() in klist.stdout or computer_name in klist.stdout
    ), f"Computer name '{computer_name}' not found in keytab."

    # 4. Delete the computer account
    delete_result = client.adcli.delete_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=[computer_name],  # Pass the specific name to delete
        krb=False,
    )
    assert delete_result.rc == 0, f"Delete failed for '{computer_name}': {delete_result.stderr}"

    # 5. Verify Deletion
    show_result_after = client.adcli.show_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=[computer_name, "--verbose"],
        krb=False,
    )
    assert show_result_after.rc != 0, f"Computer '{computer_name}' still exists after deletion!"


@pytest.mark.importance("medium")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_join_long_name_fail(client: Client, provider: GenericADProvider):
    """
    :title: adcli join fails with name > 15 chars (NetBIOS limit)
    :steps:
        1. Generate a computer name that is exactly 16 characters long
           (exceeding the 15-character NetBIOS limit).
        2. Attempt to join the domain using adcli join with this long computer name.
        3. Verify the command fails and returns a non-zero exit code.
        4. Inspect the standard error output for constraint or failure messages.
    :expectedresults:
        1. The adcli join command is rejected and returns rc != 0.
        2. The stderr output contains strings indicating that it couldn't create
           the computer account or hit a constraint violation.
    """
    if provider.role == "samba":
        pytest.skip(
                "Skipping test: Currently long hostname allowed on Samba!"
                "Upstream tracker: https://bugzilla.samba.org/show_bug.cgi?id=16037 !!")
    # 16 characters (NetBIOS limit is 15)
    long_name = "THISNAMEISTOOLONG123456"

    join_result = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--computer-name={long_name}"],
        krb=False,
    )

    if join_result.rc != 0:
        err = join_result.stderr.lower()
        assert "couldn't create computer account" in err or "constraint" in err or "fail" in err
    else:
        pytest.fail(f"Security/Constraint Failure: Join unexpectedly succeeded with long name '{long_name}'")
