"""adcli test cases"""

from __future__ import annotations

import re
import uuid

import pytest
from sssd_test_framework.roles.client import Client
from sssd_test_framework.roles.generic import GenericADProvider

from .topology import KnownTopology, KnownTopologyGroup


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_info(client: Client, provider: GenericADProvider):
    """
    :title: adcli look up a AD-domain
    :steps:
        1. Query a specified AD-domain
    :expectedresults:
        1. AD-domain information is properly fetched
    """
    info = client.adcli.info(domain=provider.host.domain, args=["--verbose"])
    assert info.rc == 0, "adcli info command failed!"
    assert provider.host.domain in info.stderr, "adcli failed to fetch domain info!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_join(client: Client, provider: GenericADProvider):
    """
    :title: adcli join AD-domain
    :steps:
        1. Join the client to a AD-domain
    :expectedresults:
        1. A computer account and related keytabs of client should be created on AD-domain
    """
    join_command = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    short_hostname = client.host.hostname.split(".")[0].upper()
    assert join_command.rc == 0, "adcli failed to join the client!"
    assert re.findall(
        rf"Retrieved kvno .* for computer account in directory.*CN={short_hostname}",
        join_command.stderr,
        re.IGNORECASE,
    ), "adcli failed to join the client!"
    assert re.findall(
        rf"Added the entries to the keytab: host.{short_hostname}.* FILE:/etc/krb5.keytab",
        join_command.stderr,
        re.IGNORECASE,
    ), "adcli failed to join the client!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_show_computer(client: Client, provider: GenericADProvider):
    """
    :title: adcli show computer
    :setup:
        1. Join the client account in the AD
    :steps:
        1. Request information about a client computer account stored in AD-domain
    :expectedresults:
        1. Correct information about the requested client account is fetched from the AD-domain
    """
    client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    show_computer = client.adcli.show_computer(
        domain=provider.host.domain,
        args=["--login-user", "Administrator", "--verbose"],
        login_user="Administrator",
        krb=False,
        password=provider.host.adminpw,
    )

    short_hostname = client.host.hostname.split(".")[0].upper()
    assert re.findall(
        rf"Retrieved kvno .* for computer account in directory.*CN={short_hostname}",
        show_computer.stderr,
        re.IGNORECASE,
    ), "adcli failed to show computer info!"
    assert show_computer.rc == 0, "adcli failed showing computer info!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_delete_computer(client: Client, provider: GenericADProvider):
    """
    :title: adcli delete computer
    :setup:
        1. Join the client account in the AD
    :steps:
        1. Delete a client computer account from the AD-domain
    :expectedresults:
        1. Requested client computer account is correctly deleted from AD-Domain
    """
    short_hostname = client.host.hostname.split(".")[0].upper()

    client.adcli.join(
        domain=f"{provider.host.domain}",
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    delete_computer = client.adcli.delete_computer(
        domain=f"{provider.host.domain}",
        args=["--login-user", "Administrator", "--verbose"],
        krb=False,
        login_user="Administrator",
        password=provider.host.adminpw,
    )

    assert re.findall(
        rf"Deleted computer account at: CN={short_hostname}", delete_computer.stderr, re.IGNORECASE
    ), "adcli showing computer info!"

    show_computer = client.adcli.show_computer(
        domain=f"{provider.host.domain}",
        args=["--login-user", "Administrator", "--verbose"],
        login_user="Administrator",
        krb=False,
        password=provider.host.adminpw,
    )

    assert show_computer.rc != 0, "adcli showing computer info!"

    assert re.findall(
        r"No computer account for .* exists", show_computer.stderr, re.IGNORECASE
    ), "adcli showing deleted computer info!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_testjoin(client: Client, provider: GenericADProvider):
    """
    :title: adcli testjoin AD-domain
    :setup:
        1. Join the client to a AD-domain
    :steps:
        1. Run testjoin to verify check if the client is joined to the AD-domain
    :expectedresults:
        1. The join is active
    """
    client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    testjoin = client.adcli.testjoin(
        domain=provider.host.domain, args=[f"--domain-controller={provider.host.hostname}", "--verbose"]
    )
    assert testjoin.rc == 0, "client-join is not valid!"
    assert re.findall(
        rf"Sucessfully validated join to domain {provider.host.domain}", testjoin.stdout, re.IGNORECASE
    ), "Failed to validate join to domain!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_join_and_delete_with_modified_hostname(client: Client, provider: GenericADProvider):
    """
    :title: adcli join AD-domain with a modified hostname
    :description: Verifies a client can be joined to and deleted from AD domain after its
        hostname has been changed locally.
    :setup:
        1. Modify the client's hostname.
    :steps:
        1. Join the client to the AD-domain using the new hostname.
        2. Verify the computer account was created in AD with the new hostname.
        3. Delete the computer account
    :expectedresults:
        1. The domain join is successful.
        2. The computer account in AD matches the modified client hostname.
        3. Computer Account should be deleted from AD
    """
    # New hostname
    unique_id = str(uuid.uuid4())[:4]
    new_hostname = f"newclient-{unique_id}.{provider.host.domain}"

    client.hostnameutils.name = new_hostname
    assert client.hostnameutils.name == new_hostname

    # Join with the new hostname
    join_command = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    # The computer account name in AD will be the short hostname, uppercased
    new_short_hostname = new_hostname.split(".")[0].upper()

    assert join_command.rc == 0, f"adcli failed to join with modified hostname: {join_command.stderr}!"
    assert re.search(
        rf"Retrieved kvno .* for computer account in directory.*CN={new_short_hostname}",
        join_command.stderr,
        re.IGNORECASE,
    ), "Computer account was not created correctly with the modified hostname!"

    client.adcli.delete_computer(
        domain=f"{provider.host.domain}",
        args=["--login-user", "Administrator", "--verbose"],
        krb=False,
        login_user="Administrator",
        password=provider.host.adminpw,
    )

    show_computer = client.adcli.show_computer(
        domain=f"{provider.host.domain}",
        args=["--login-user", "Administrator", "--verbose"],
        login_user="Administrator",
        krb=False,
        password=provider.host.adminpw,
    )

    assert show_computer.rc != 0, "adcli showing computer info!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_join_with_short_hostname(client: Client, provider: GenericADProvider):
    """
    :title: adcli join AD-domain with a short hostname
    :description: Verifies a client can join an AD domain after its hostname has been changed to a short name.
    :setup:
        1. Modify the client's hostname to a short name.
    :steps:
        1. Join the client to the AD-domain using the new short hostname.
        2. Verify the computer account was created in AD with the new short hostname.
    :expectedresults:
        1. The domain join is successful.
        2. The computer account in AD matches the modified client short hostname.
    """
    # Define a new short hostname
    unique_id = str(uuid.uuid4())[:4]
    new_hostname = f"shortname-{unique_id}"

    # Change hostname
    client.hostnameutils.name = new_hostname
    assert client.hostnameutils.shortname == new_hostname

    # Join with new hostname
    join_command = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    # The computer account name in AD will be the short hostname, uppercased
    new_short_hostname_upper = new_hostname.upper()

    assert join_command.rc == 0, f"adcli failed to join with modified short hostname: {join_command.stderr}!"
    assert re.search(
        rf"Retrieved kvno .* for computer account in directory.*CN={new_short_hostname_upper}",
        join_command.stderr,
        re.IGNORECASE,
    ), "Computer account was not created correctly with the modified short hostname!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_testjoin_client_with_different_domainname(client: Client, provider: GenericADProvider):
    """
    :title: adcli testjoin client with a different domain
    :description: Verifies adcli testjoin should detect domain correctly for client with different domainname
    :setup:
        1. Set the client's hostname to a different domain than DC-domain.
        2. Join the client to the AD-domain using the changed DNS hostname.
    :steps:
        1. Verify the testjoin can detect and contact the correct domain controller
    :expectedresults:
        1. Adcli testjoin is able to detect and contact correct domain controller.
    """
    # different domain name
    new_hostname = "newclient.host.domain"

    # Change the hostname
    client.hostnameutils.name = new_hostname

    # Join with new hostname
    client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    # Run testjoin to verify if it is able to contact correct DC
    testjoin_command = client.adcli.testjoin(
        domain=provider.host.domain, args=[f"--domain-controller={provider.host.hostname}", "--verbose"]
    )

    assert testjoin_command.rc == 0, "adcli testjoin does not detect domain name correctly!"
    assert re.search(
        rf"Sucessfully validated join to domain.*{provider.host.domain}",
        testjoin_command.stdout,
        re.IGNORECASE,
    ), "adcli testjoin does not detect domain name correctly!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_passwd_user(client: Client, provider: GenericADProvider):
    """
    :title: adcli change user password
    :description: Verifies that adcli can successfully change a user's password in AD.
    :setup:
        1. Create a user in the AD domain.
        2. Set an initial password for the new user.
    :steps:
        1. Use adcli to change the user's password twice from the old to the new one.
        2. Attempt to authenticate (kinit) as the user with the new password.
        3. Attempt to authenticate (kinit) as the user with the old password.
    :expectedresults:
        1. The password change command succeeds.
        2. Authentication with the new password succeeds.
        3. Authentication with the old password fails.
    """
    unique_id = str(uuid.uuid4())[:8]
    target_user = f"pwduser-{unique_id}"
    old_password = "InitialPassword123!"
    new_password = "NewerPassword456!"

    client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    u = client.adcli.create_user(
        target_user,
        domain=provider.host.domain,
        args=["--verbose"],
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        krb=False,
    )

    assert u.rc == 0, f"Failed to create user '{target_user}': {u.stderr}!"

    p = client.adcli.passwd_user(
        user=target_user,
        new_password=old_password,
        domain=provider.host.domain,
        args=["--verbose"],
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
    )
    assert p, f"Failed to set initial password: {p.stderr}!"

    # Change the user's password from old to new, using the parameterized auth method
    s = client.adcli.passwd_user(
        user=target_user,
        new_password=new_password,
        domain=provider.host.domain,
        args=["--verbose"],
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
    )

    assert s, f"adcli passwd-user failed: {s.stderr}!"

    # 1. Verify new password works by getting a Kerberos ticket
    kinit_with_new = client.host.conn.exec(
        ["kinit", f"{target_user}@{provider.host.domain.upper()}"],
        input=f"{new_password}\n",
        raise_on_error=True,
    )

    assert kinit_with_new.rc == 0, "Authentication with new password failed!"

    # 2. Verify old password no longer works
    kinit_with_old = client.host.conn.exec(
        ["kinit", f"{target_user}@{provider.host.domain.upper()}"],
        input=f"{old_password}\n",
        raise_on_error=False,
    )
    assert kinit_with_old.rc != 0, "Authentication with old password unexpectedly succeeded!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_aduser_create_delete(client: Client, provider: GenericADProvider):
    """
    :title: adcli create, delete ADuser
    :description: adcli create, delete user in AD
    :setup:
        1. Join client to AD.
    :steps:
        1. Create AD user.
        2. Delete AD-user.
    :expectedresults:
        1. AD-user is created successfully.
        2. AD-user is deleted successfully.
    """
    aduser = "aduser12"

    client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)

    c = client.adcli.create_user(
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert c.rc == 0, "User creation failed!"

    u_id = client.tools.id(f"{aduser}@{provider.host.domain}")

    assert u_id.memberof([f"domain users@{provider.host.domain}"]), "AD-user is not detected!"

    d = client.adcli.delete_user(
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    assert d.rc == 0, "User deletion failed!"

    client.sssctl.cache_expire(user=aduser)

    assert client.tools.id(f"{aduser}@{provider.host.domain}") is None, f"{aduser} is not deleted!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_create_msa(client: Client, provider: GenericADProvider):
    """
    :title: adcli create msa
    :description: adcli create msa
    :setup:
        1. Join client to AD.
    :steps:
        1. Create msa account
    :expectedresults:
        1. account is created
    """
    msa = client.adcli.create_msa(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert msa.rc == 0, "Managed service account is not created!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_create_delete_group(client: Client, provider: GenericADProvider):
    """
    :title: adcli create,delete group
    :description: adcli create, delete group
    :setup:
        1. Join client to AD.
    :steps:
        1. Create AD-group
        2. Delete AD-group
    :expectedresults:
        1. AD-group created successfully
        2. AD-group deleted successfully
    """

    client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)

    create_group = client.adcli.create_group(
        "adgroup",
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    assert create_group.rc == 0, "AD-group is not created!"

    delete_group = client.adcli.delete_group(
        "adgroup",
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    assert delete_group.rc == 0, "AD-group is not deleted!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_add_remove_group_member(client: Client, provider: GenericADProvider):
    """
    :title: adcli add, remove member to a group
    :description: adcli add and remove member to a group
    :setup:
        1. Join client to AD.
        2. Create AD-group
        3. Create AD-user
    :steps:
        1. Add AD-user to AD-group
        2. Remove AD-user from AD-group
    :expectedresults:
        1. AD-user has AD-group membership
        2. AD-user has left the AD-group membership
    """
    new_password = "NewerPassword456!"
    adgroup = "adgroup"
    aduser = "aduser"

    client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)

    client.adcli.create_group(
        adgroup,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    client.adcli.create_user(
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    client.adcli.passwd_user(
        user=aduser,
        new_password=new_password,
        domain=provider.host.domain,
        args=["--verbose"],
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
    )

    client.adcli.add_member(
        adgroup,
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    result = client.tools.id(f"{aduser}@{provider.host.domain}")

    assert result.memberof([f"{adgroup}@{provider.host.domain}"]), "AD-user is not added to AD-group!"

    client.adcli.remove_member(
        adgroup,
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )

    client.sssctl.cache_expire(user=aduser)
    r = client.tools.id(f"{aduser}@{provider.host.domain}")

    assert not r.memberof([f"{adgroup}@{provider.host.domain}"]), "AD-user membership not updated!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_aduser_create_posix_user(client: Client, provider: GenericADProvider):
    """
    :title: adcli create POSIX ADuser
    :description: create POSIX ADuser
    :setup:
        1. Join client to AD.
    :steps:
        1. Create POSIX AD user.
    :expectedresults:
        1. POSIX AD-user is created successfully.
    """
    aduser = "aduser12"

    client.realm.join(
        provider.host.domain,
        krb=False,
        user=provider.host.adminuser,
        args=["--automatic-id-mapping=no"],
        password=provider.host.adminpw,
    )

    c = client.adcli.create_user(
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=[
            "--verbose",
            "--unix-uid=11111",
            "--unix-gid=11111",
            "--unix-shell=/bin/bash",
            f"--unix-home=/home/{aduser}",
        ],
        krb=False,
        password=provider.host.adminpw,
    )

    assert c.rc == 0, "aduser creation failed!"

    client.sssd.stop()
    client.sssd.clear(db=True, memcache=True, logs=True)
    client.sssd.start(apply_config=False, check_config=False)

    g = client.tools.getent.passwd(f"{aduser}@{provider.host.domain}")

    assert g.uid == 11111, "AD-user posix-attribute not detected!"
    assert g.gid == 11111, "AD-user posix-attribute not detected!"
    assert g.home == f"/home/{aduser}", "AD-user posix-attribute not detected!"
    assert g.shell == "/bin/bash", "AD-user posix-attribute not detected!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_after_join_show_details(client: Client, provider: GenericADProvider):
    """
    :title: after adcli join show details of join operation
    :steps:
        1. Join the client to a AD-domain
    :expectedresults:
        1. A computer account and related keytabs of client should be created on AD-domain
    """
    short_hostname = client.host.hostname.split(".")[0].upper()

    j = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose", "--show-details"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert j.rc == 0, "adcli failed to join the client!"

    assert re.findall(
        rf"domain-name = {provider.host.domain}\ndomain-realm = {provider.host.domain.upper()}\n",
        j.stdout,
        re.IGNORECASE,
    ), "adcli stdout failed to show domain information!"

    assert re.findall(
        rf"\[computer\]\nhost-fqdn = {client.host.hostname}\ncomputer-name = {short_hostname}",
        j.stdout,
        re.IGNORECASE,
    ), "adcli stdout failed to show computer information!"

    assert re.findall(
        r"\[keytab\]\nkvno = [0-9]+\nkeytab = FILE:/etc/krb5.keytab", j.stdout, re.IGNORECASE
    ), "adcli stdout failed to show computer information!"
