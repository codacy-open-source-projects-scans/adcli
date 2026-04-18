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
        rf"Successfully validated join to domain {provider.host.domain}", testjoin.stdout, re.IGNORECASE
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
        rf"Successfully validated join to domain.*{provider.host.domain}",
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


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_add_details_at_join(client: Client, provider: GenericADProvider):
    """
    :title: add details in computer account at joining
    :steps:
        1. At joining, add details about OS, OS version, OS service pack, short-description, the client to a AD-domain
    :expectedresults:
        1. After join, computer account wil show added details in computer account
    """
    args = ["--verbose"]
    details = {
        "--os-name": "linux",
        "--os-service-pack": "99",
        "--os-version": "10",
        "--description": "Set during joining",
    }
    output = {
        "operatingSystem": "linux",
        "operatingSystemVersion": "10",
        "operatingSystemServicePack": "99",
        "description": "Set During joining",
    }

    for i, j in details.items():
        args.append(f"{i}={j}")

    k = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=args,
        krb=False,
    )

    assert k.rc == 0, "adcli failed to join the client!"

    s = client.adcli.show_computer(
        domain=provider.host.domain,
        args=["--login-user", "Administrator", "--verbose"],
        login_user="Administrator",
        krb=False,
        password=provider.host.adminpw,
    )
    assert s.rc == 0, "adcli failed to show the client details!"

    for attribute, value in output.items():
        assert re.findall(
            rf"{attribute}:\n {value}", s.stdout, re.IGNORECASE
        ), f"{attribute} Details added at join not reflected!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
@pytest.mark.parametrize("expire_value", ["Yes", "No", "True", "False"])
def test_adcli_control_machine_account_passwd_expiry(client: Client, provider: GenericADProvider, expire_value: str):
    """
    :title: Control machin account password expiry
    :steps:
        1. At joininig, add dont-expire-password with values
    :expectedresults:
        1. After join, computer account password attribute would show correct details
    """

    j = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--dont-expire-password={expire_value}"],
        krb=False,
    )

    assert j.rc == 0, "adcli failed to join the client!"

    s = client.adcli.show_computer(
        domain=provider.host.domain,
        args=["--login-user", "Administrator", "--verbose"],
        login_user="Administrator",
        krb=False,
        password=provider.host.adminpw,
    )
    assert s.rc == 0, "adcli failed to show the client details!"

    uac_match = re.search(r"userAccountControl:\s*(\d+)", s.stdout)

    uac_value = int(uac_match.group(1))

    # 4. Bitwise Verification
    # Check if the "Don't Expire" bit is set
    # 0x10000 = ADS_UF_DONT_EXPIRE_PASSWD
    ads_uf_dont_expire_passwd = 0x10000
    is_flag_set = (uac_value & ads_uf_dont_expire_passwd) == ads_uf_dont_expire_passwd

    if expire_value in ("True", "Yes"):
        assert is_flag_set, (
            f"Failure: Password should NOT expire, but 'ads_uf_dont_expire_passwd' (0x10000) is MISSING.\n"
            f"UAC Value: {uac_value}"
        )
    else:
        assert not is_flag_set, (
            f"Failure: Password should expire, but 'ads_uf_dont_expire_passwd' (0x10000) is SET.\n"
            f"UAC Value: {uac_value}"
        )


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_show_password_at_join(client: Client, provider: GenericADProvider):
    """
    :title: After join, show computer account password
    :steps:
        1. Run join operation with `--show-password`.
    :expectedresults:
        1. Successful adcli join output should show computer account password.
    """
    j = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", "--show-password"],
        krb=False,
    )

    assert j.rc == 0, "adcli failed to join the client!"

    assert re.findall(
        r"\[computer\]\ncomputer-password = .*", j.stdout, re.IGNORECASE
    ), "computer account password at join not reflected!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_user_principal_at_join(client: Client, provider: GenericADProvider):
    """
    :title: At join, set computer's kerberos principal with userPrincipal.
    :steps:
        1. Run join operation with `--userPrincipal` with value.
    :expectedresults:
        1. Successful adcli join should set computer kerberos principal as per userPrincipalName.
    """
    j = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--user-principal=host/setatjoin@{provider.host.domain.upper()}"],
        krb=False,
    )

    assert j.rc == 0, "adcli failed to join the client!"

    klist = client.host.conn.exec(
        ["klist", "-kt"],
        raise_on_error=True,
    )
    assert re.findall(
        rf"host/setatjoin@{provider.host.domain.upper()}", klist.stdout, re.IGNORECASE
    ), "userPrincipal value not set!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_join_hostname_length(client: Client, provider: GenericADProvider):
    """
    :title: Join a client having hostname length 19-character or more
    :setup:
        1. Set client hostname to 19-character length.
    :steps:
        1. Run join
    :expectedresults:
        1. Join operation should truncate hostname to required length and succeed.
    """
    u = str(uuid.uuid4())[:20]
    new_hostname = f"client-{u}.{provider.host.domain}"

    client.hostnameutils.name = new_hostname
    assert client.hostnameutils.name == new_hostname

    j = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose"],
        krb=False,
    )

    assert j.rc == 0, "adcli failed to join the client!"
    assert re.findall(
        rf"Truncated computer account name from fqdn: {new_hostname[:15].upper()}", j.stderr, re.IGNORECASE
    ), "adcli join failed!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_preset_reset_computer(client: Client, provider: GenericADProvider):
    """
    :title: Preset reset a computer account in AD
    :steps:
        1. Preset a computer account in AD with --one-time-password value
        2. Join client with --one-time-password authentication
        3. Reset a computer account in AD
        4. Delete the computer account in AD
    :expectedresults:
        1. A computer account be created in AD
        2. Join operation should succeed with --one-time-password  value
        3. A computer account will be reset in AD
        4. Computer object deleted from AD
    """
    if provider.role == "samba":
        d = client.adcli.delete_computer(
            domain=f"{provider.host.domain}",
            args=["--login-user", "Administrator", "--verbose"],
            krb=False,
            login_user="Administrator",
            password=provider.host.adminpw,
        )
        assert d.rc is not None

    j = client.adcli.preset_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", "--one-time-password", "redhat", client.host.hostname],
        krb=False,
    )

    assert j.rc == 0, "adcli failed to preset the client!"

    assert re.findall(r"Created computer account", j.stderr, re.IGNORECASE), "adcli preset failed!"

    client.host.conn.exec(
        ["adcli", "join", "--verbose", "--one-time-password", "redhat", f"--domain={provider.host.domain}"]
    )

    z = client.adcli.reset_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", client.host.hostname],
        krb=False,
    )

    assert z.rc == 0, "adcli failed to join the client!"

    delete_computer = client.adcli.delete_computer(
        domain=f"{provider.host.domain}",
        args=["--login-user", "Administrator", "--verbose"],
        krb=False,
        login_user="Administrator",
        password=provider.host.adminpw,
    )

    assert re.findall(
        r"Deleted computer account at", delete_computer.stderr, re.IGNORECASE
    ), "adcli showing computer info!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_msa_service_principal(client: Client, provider: GenericADProvider):
    """
    :title: adcli msa add service principal
    :description: adcli add service principal msa
    :setup:
        1. join client to ad.
    :steps:
        1. create msa account
    :expectedresults:
        1. account is created
    """
    client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)
    msa = client.adcli.create_msa(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert msa.rc == 0, "managed service account is not created!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_update_description(client: Client, provider: GenericADProvider):
    """
    :title: adcli update computer description
    :description: Join domain with a description, then update it using 'adcli update'.
    :setup:
        1. Join the client to the AD domain with an initial description.
    :steps:
        1. Verify the initial description using 'adcli show-computer'.
        2. Run 'adcli update' with a new '--description'.
        3. Verify the new description using 'adcli show-computer'.
    :expectedresults:
        1. Initial description is set correctly.
        2. Update command succeeds.
        3. New description is updated in AD.
    """
    initial_desc = "during join"
    new_desc = "chagneddd"

    # 1. Join with initial description
    join_cmd = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--description={initial_desc}"],
        krb=False,
    )
    assert join_cmd.rc == 0, f"adcli join failed: {join_cmd.stderr}"
    # client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)

    # 2. Verify initial description
    show_cmd_1 = client.adcli.show_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose"],
        krb=False,
    )
    assert show_cmd_1.rc == 0, f"adcli show-computer failed: {show_cmd_1.stderr}"

    # 3. Update description using machine credentials (implicit keytab auth)
    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--description={new_desc}"],
    )
    assert update_cmd.rc == 0, f"adcli update failed: {update_cmd.stderr}"
    # 4. Verify new description
    show_cmd_2 = client.adcli.show_computer(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose"],
        krb=False,
    )
    assert show_cmd_2.rc == 0, f"adcli show-computer failed: {show_cmd_2.stderr}"
    output_2 = show_cmd_2.stdout + show_cmd_2.stderr
    assert re.search(
        rf"description:\n.*{new_desc}", output_2, re.IGNORECASE
    ), f"New description '{new_desc}' not found in computer details."


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_update_msa_service_principal(client: Client, provider: GenericADProvider):
    """
    :title: adcli update msa add service principal
    :description: adcli update add service principal msa
    :setup:
        1. join client to ad.
        2. create msa account
    :steps:
        1. update a service principal of msa account
    :expectedresults:
        1. service principal is updated
    """
    msa = client.adcli.create_msa(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert msa.rc == 0, "managed service account is not created!"

    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=[
            "--verbose",
            f"--add-service-principal=HTTPD/{provider.host.domain}",
            f"--host-keytab=/etc/krb5.keytab.{provider.host.domain}",
        ],
    )
    assert update_cmd.rc == 0, f"adcli update failed: {update_cmd.stderr}"
    output = update_cmd.stdout + update_cmd.stderr
    assert re.search(rf"HTTPD/{provider.host.domain}", output, re.IGNORECASE), "service principal not updated!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_create_msa_with_correct_selinux(client: Client, provider: GenericADProvider):
    """
    :title: adcli create-msa create keytab with correct seliux context
    :setup:
        1. Join the domain.
    :steps:
        1. Create a Managed Service Account (MSA) using adcli.
        2. Verify the MSA keytab is created and has correct SELinux context.
        3. Verify adcli update works using the new host keytab.
    :expectedresults:
        1. MSA created successfully
        2. keytab is created with correct selinux context
        3. adcli update works with new host keytab
    """
    s = client.host.conn.exec(["getenforce"], raise_on_error=False)
    if s.rc != 0:
        pytest.skip("getenforce command is not available or failed. Skipping the test!")
    elif "Disabled" in s.stdout:
        pytest.skip("SELinux is disabled on client host. Skipping the test!")
    join_result = client.realm.join(
        domain=provider.host.domain,
        user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", "--client-software=sssd", "--membership-software=adcli"],
        krb=False,
    )
    assert join_result.rc == 0, f"Join failed: {join_result.stderr}"

    msa_keytab_path = f"/etc/krb5.keytab.{provider.host.domain}"

    client.adcli.create_msa(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose"],
        krb=False,
    )

    assert client.host.fs.exists(msa_keytab_path), f"MSA Keytab file {msa_keytab_path} was not created."

    ls_cmd = client.host.conn.exec(["ls", "-lZ", msa_keytab_path])
    assert (
        "krb5_keytab_t" in ls_cmd.stdout
    ), f"SELinux context incorrect for {msa_keytab_path}.\nOutput: {ls_cmd.stdout}"

    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        args=["--verbose", f"--host-keytab={msa_keytab_path}"],
    )

    assert update_cmd.rc == 0, f"adcli update failed using the new MSA keytab!\n" f"Stderr: {update_cmd.stderr}"
    ls_upd = client.host.conn.exec(["ls", "-lZ", msa_keytab_path])
    assert (
        "krb5_keytab_t" in ls_upd.stdout
    ), f"SELinux context incorrect for {msa_keytab_path}.\nOutput: {ls_cmd.stdout}"


def get_max_kvno(klist_output: str, principal_match: str) -> int:
    """
    Helper function to extract the highest KVNO for a specific principal
    from 'klist -kt' output.
    """
    kvnos = []
    # klist -kt output format typically looks like:
    #    4 12/24/2025 00:31:01 host/cli1.test.qe@TEST.QE
    for line in klist_output.splitlines():
        if principal_match in line:
            # Match the first integer at the beginning of the line
            match = re.match(r"^\s*(\d+)\s+", line)
            if match:
                kvnos.append(int(match.group(1)))

    return max(kvnos) if kvnos else -1


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_update_increment_kvno(client: Client, provider: GenericADProvider):
    """
    :title: Verify adcli update increments KVNO using explicit --host-fqdn
    :setup:
        1. Join the domain to establish initial keytab.
    :steps:
        1. Read initial KVNO from the keytab.
        2. Run 'adcli update' specifying the --host-fqdn parameter.
        3. Read new KVNO from the keytab
    :expectedresults:
        1. Successfully read KVNO from the keytab.
        2. Successfully executed adcli
        4. New KVNO from the keytab has incremented.
    """
    # 1. Join Domain (Creates initial /etc/krb5.keytab)
    join_result = client.realm.join(
        domain=provider.host.domain,
        user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", "--client-software=sssd", "--membership-software=adcli"],
        krb=False,
    )
    assert join_result.rc == 0, f"Join failed: {join_result.stderr}"

    # 2. Get Initial KVNO
    host_principal = f"host/{client.host.hostname}"

    klist_initial = client.host.conn.exec(["klist", "-kt"])
    assert klist_initial.rc == 0, "Failed to read initial keytab with klist"

    initial_kvno = get_max_kvno(klist_initial.stdout, host_principal)
    assert initial_kvno != -1, f"Could not find principal {host_principal} in initial keytab"

    # 3. Run adcli update with --host-fqdn
    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        args=["--verbose", f"--host-fqdn={client.host.hostname}", "--computer-password-lifetime=0"],
    )

    # 4. Assert Update Success
    assert update_cmd.rc == 0, (
        f"adcli update failed!\n" f"Return Code: {update_cmd.rc}\n" f"Stderr: {update_cmd.stderr}"
    )

    # 5. Get New KVNO and Verify Increment
    klist_updated = client.host.conn.exec(["klist", "-kt"])
    assert klist_updated.rc == 0, "Failed to read updated keytab with klist"

    new_kvno = get_max_kvno(klist_updated.stdout, host_principal)
    assert new_kvno != -1, f"Could not find principal {host_principal} in updated keytab"

    # Assert that the KVNO has strictly increased
    assert new_kvno > initial_kvno, (
        f"KVNO did not increment after adcli update! " f"Initial: {initial_kvno}, New: {new_kvno}"
    )


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_update_with_host_fqdn(client: Client, provider: GenericADProvider):
    """
    :title: Verify adcli update using explicit --host-fqdn
    :setup:
        1. Join the domain to establish initial keytab.
    :steps:
        1. Run 'adcli update' specifying the --host-fqdn
        2. Verify the keytab is valid and contains principals.
    :expectedresults:
        1. adcli command executes correctly
        2. keytab shows host principal correctly
    """

    join_result = client.realm.join(
        domain=provider.host.domain,
        user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose"],
    )
    assert join_result.rc == 0, f"Join failed: {join_result.stderr}"

    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        args=["--verbose", f"--host-fqdn={client.host.hostname}"],
    )

    assert update_cmd.rc == 0, (
        f"adcli update failed!\n" f"Return Code: {update_cmd.rc}\n" f"Stderr: {update_cmd.stderr}"
    )

    # 4. Verify Keytab
    klist_cmd = client.host.conn.exec(["klist", "-kt"])
    assert klist_cmd.rc == 0, "Failed to read keytab with klist"

    # Verify we see the host principal (e.g., host/cli1.test.qe)
    assert f"host/{client.host.hostname}" in klist_cmd.stdout, "Keytab does not contain the expected host principal"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_update_service_principal(client: Client, provider: GenericADProvider):
    """
    :title: adcli update to add service principal in keytab
    :setup:
        1. Join the client to a AD-domain
    :steps:
        1. Add a service principal in keytab
    :expectedresults:
        1. A keytab contains added service principal
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

    update_cmd = client.adcli.update(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=[
            "--verbose",
            f"--add-service-principal=HTTPD/{provider.host.domain}",
            "--host-keytab=/etc/krb5.keytab",
            short_hostname,
        ],
    )
    assert update_cmd.rc == 0, f"adcli update failed: {update_cmd.stderr}"
    output = update_cmd.stdout + update_cmd.stderr
    assert re.search(rf"HTTPD/{provider.host.domain}", output, re.IGNORECASE), "service principal not updated!"


@pytest.mark.importance("critical")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_aduser_pre_filter_user(client: Client, provider: GenericADProvider):
    """
    :title: adcli filter username before create an ADuser
    :description: adcli filter username before create ADuser
    :setup:
        1. Join client to AD.
    :steps:
        1. Create AD user having @ in name
    :expectedresults:
        1. AD-user is not created
    """
    aduser = "aduser@12"

    client.realm.join(provider.host.domain, krb=False, user=provider.host.adminuser, password=provider.host.adminpw)

    c = client.adcli.create_user(
        aduser,
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=provider.host.adminpw,
    )
    assert c.rc != 0, "Sanity filtering of username before user creation failed!"


@pytest.mark.importance("high")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_managedby_attribute(client: Client, provider: GenericADProvider):
    """
    :title: Populate and update the managedBy attribute on the computer account
    :setup:
        1. Fetch the Base DN dynamically via PowerShell (naming_context).
        2. Construct valid DNs for Administrator and Guest users.
    :steps:
        1. Join the domain using adcli join, passing --setattr=managedBy=<Administrator_DN>.
        2. Verify the managedBy attribute using native PowerShell on the DC.
        3. Update the attribute to the Guest user using adcli update.
        4. Verify the updated attribute using native PowerShell on the DC.
    """
    if provider.role == "samba":
        pytest.skip("Skipping test: NO Powershell on Samba!!")
    base_dn = provider.host.naming_context
    admin_dn = f"CN=Administrator,CN=Users,{base_dn}"
    guest_dn = f"CN=Guest,CN=Users,{base_dn}"

    computer_sam = f"{client.host.hostname.split('.')[0].upper()}$"

    def get_managed_by_pwsh() -> str:
        cmd = f'Get-ADComputer -Identity "{computer_sam}" -Properties managedBy | Select-Object -ExpandProperty managedBy'
        result = provider.host.conn.run(cmd)

        assert result.rc == 0, f"Failed to query AD computer: {result.stderr}"

        managed_by = result.stdout.strip()
        assert managed_by, f"'managedBy' attribute is empty for {computer_sam}."
        return managed_by

    join_result = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--setattr=managedBy={admin_dn}"],
        krb=False,
    )
    assert join_result.rc == 0, f"Join failed: {join_result.stderr}"

    initial_attr = get_managed_by_pwsh()
    assert initial_attr.lower() == admin_dn.lower(), f"Expected {admin_dn}, but AD returned {initial_attr}"

    update_result = client.adcli.update(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--setattr=managedBy={guest_dn}"],
    )
    assert update_result.rc == 0, f"Update failed: {update_result.stderr}"

    updated_attr = get_managed_by_pwsh()
    assert updated_attr.lower() == guest_dn.lower(), f"Expected {guest_dn}, but AD returned {updated_attr}"


def set_des_key_only_flag(provider: GenericADProvider, computer_sam: str, enable: bool):
    """
    Modifies the USE_DES_KEY_ONLY flag (0x200000) on an AD computer account
    using native PowerShell execution.
    """
    if enable:
        math_op = "-bor 0x200000"
    else:
        math_op = "-band (-bnot 0x200000)"

    pwsh_script = f"""
    $comp = Get-ADComputer -Identity '{computer_sam}' -Properties userAccountControl
    if (-not $comp) {{
        Write-Error "Computer {computer_sam} not found in AD."
        exit 1
    }}

    $newUAC = $comp.userAccountControl {math_op}
    Set-ADComputer -Identity '{computer_sam}' -Replace @{{userAccountControl=$newUAC}}
    """
    result = provider.host.conn.run(pwsh_script)
    assert result.rc == 0, f"Failed to modify USE_DES_KEY_ONLY flag: {result.stderr}"


@pytest.mark.importance("high")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_resets_des_flag_on_precreated_computer(client: Client, provider: GenericADProvider):
    """
    :title: Verify adcli resets the USE_DES_KEY_ONLY flag when joining a pre-created account
    :setup:
        1. Calculate the expected computer name and sAMAccountName.
        2. Pre-create the computer object natively in AD via PowerShell.
        3. Enable the USE_DES_KEY_ONLY flag on the object.
    :steps:
        1. Join the domain using adcli join.
        2. Query the userAccountControl attribute natively in AD.
    :expectedresults:
        1. adcli join reset USE_DES_KEY_ONLY flag of computer.
        2. The flag USE_DES_KEY_ONLY flag (the 0x200000 bit is 0) on computer object is cleared.
    """
    if provider.role == "samba":
        pytest.skip("Skipping test: NO Powershell on Samba!!")
    comp_name = client.host.hostname.split(".")[0].upper()
    computer_sam = f"{comp_name}$"

    setup_script = f"""
    if (-not (Get-ADComputer -Filter "SamAccountName -eq '{computer_sam}'")) {{
        New-ADComputer -Name '{comp_name}' -SamAccountName '{computer_sam}'
    }}

    $comp = Get-ADComputer -Identity '{computer_sam}' -Properties userAccountControl
    $newUAC = $comp.userAccountControl -bor 0x200000
    Set-ADComputer -Identity '{computer_sam}' -Replace @{{userAccountControl=$newUAC}}

    # Output the bitwise result to confirm the setup worked
    ($newUAC -band 0x200000)
    """

    setup_result = provider.host.conn.run(setup_script)
    assert setup_result.rc == 0, f"Failed to pre-create AD computer: {setup_result.stderr}"
    assert setup_result.stdout.strip() == "2097152", "Failed to set DES flag during setup."

    try:
        join_result = client.adcli.join(
            domain=provider.host.domain,
            login_user=provider.host.adminuser,
            password=provider.host.adminpw,
            args=["--verbose"],
            krb=False,
        )
        assert join_result.rc == 0, f"adcli join failed: {join_result.stderr}"

        check_script = f"(Get-ADComputer -Identity '{computer_sam}' -Properties userAccountControl).userAccountControl -band 0x200000"
        check_result = provider.host.conn.run(check_script)
        assert check_result.rc == 0, f"Failed to query AD after join: {check_result.stderr}"

        assert check_result.stdout.strip() == "0", "adcli failed to reset the USE_DES_KEY_ONLY flag!"

    finally:
        cleanup_script = f"Remove-ADComputer -Identity '{computer_sam}' -Confirm:$false"
        provider.host.conn.run(cleanup_script, raise_on_error=False)


@pytest.mark.topology(KnownTopologyGroup.AnyAD)
@pytest.mark.importance("medium")
def test_adcli_terminate_ctrl_c_password_prompt(client: Client, provider: GenericADProvider):
    """
    :title: Terminate adcli operation using ctrl+c at password prompt
    :setup:
        1. Generate an expect script on the client that spawns adcli.
        2. Wait for the interactive password prompt to appear.
    :steps:
        1. Send the ASCII Ctrl+C character (\x03) and exit with custom code 111.
        2. Assert the script returned 111 (indicating the interrupt was successfully sent).
    :expectedresults:
        1. adcli successfully receives the interrupt.
        2. The expect wrapper exits with our designated success code (111).
    """

    client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        password=provider.host.adminpw,
        args=["--verbose", f"--domain-controller={provider.host.domain}"],
        krb=False,
    )

    expect_script = f"""#!/usr/bin/expect -f
set timeout 10

spawn adcli show-computer {provider.host.domain} -S {provider.host.hostname}

expect {{
    "*Password for *" {{
        send -- "\\x03"
        # Give the signal a fraction of a second to kill the process
        sleep 0.5
        exit 111
    }}
    timeout {{
        puts stderr "Error: Timed out waiting for the password prompt."
        exit 1
    }}
    eof {{
        puts stderr "Error: adcli exited before showing the password prompt."
        # Print exactly what adcli output to the screen before crashing
        if {{[info exists expect_out(buffer)]}} {{
            puts stderr "adcli output was: $expect_out(buffer)"
        }}
        exit 2
    }}
}}
"""
    script_path = "/tmp/test_adcli_ctrl_c.exp"

    try:
        client.host.conn.run(f"cat > {script_path} <<'_EOF'\n{expect_script}\n_EOF")
        client.host.conn.run(f"chmod +x {script_path}")

        result = client.host.conn.run(script_path, raise_on_error=False)

        assert (
            result.rc == 111
        ), f"Failed to interrupt adcli. Expected custom exit code 111, got {result.rc}. Stderr: {result.stderr}"

    finally:
        client.host.conn.run(f"rm -f {script_path}", raise_on_error=False)


@pytest.mark.topology(KnownTopologyGroup.AnyAD)
@pytest.mark.importance("medium")
def test_adcli_terminate_ctrl_c(client: Client, provider: GenericADProvider):
    """
    :title: Terminate adcli network discovery using Ctrl+C
    :steps:
        1. Execute `adcli info` targeting localhost wrapped in the `timeout` command.
        2. Configure `timeout` to send a SIGINT (--signal=SIGINT) after 2 seconds.
        3. Capture the exit code of the terminated process.
    :expectedresults:
        1. The adcli process terminates cleanly upon receiving the signal.
        2. The command returns exit code 130 (which corresponds to 128 + SIGINT).
    """

    command = f"timeout --preserve-status --signal=SIGINT 2s " f"adcli info -v {provider.host.domain} -S localhost"

    result = client.host.conn.run(command, raise_on_error=False)

    assert (
        result.rc == 130
    ), f"adcli did not terminate cleanly via SIGINT. Expected exit code 130, got {result.rc}. Stderr: {result.stderr}"


@pytest.mark.topology(KnownTopologyGroup.AnyAD)
@pytest.mark.importance("high")
def test_adcli_join_delegated_user_specified_ou(client: Client, provider: GenericADProvider):
    """
    :title: adcli join domain by delegated user in specified ou
    :setup:
        1. Create a dedicated OU on the AD server.
        2. Create a standard unprivileged AD user.
        3. Delegate 'Full Control' (GA) permissions for the OU and its descendants to the user.
    :steps:
        1. Execute adcli join with delegated user and the target OU.
        2. Verify the computer object resides in the correct OU on the AD server.
    :expectedresults:
        1. The adcli join wrapper executes without throwing an exception.
        2. The computer object is found inside the delegated OU.
    """
    if provider.role == "samba":
        pytest.skip("Skipping test: NO Powershell on Samba!!")
    unique_id = str(uuid.uuid4())[:3]
    ou_name = f"DelegatedOU_{unique_id}"
    user_name = f"joinuser_{unique_id}"
    password = "DelegatedPassword123!"

    ou_dn = f"OU={ou_name},{provider.naming_context}"

    setup_script = f"""
    Import-Module ActiveDirectory
    $ErrorActionPreference = "Stop"

    # Create the target OU
    New-ADOrganizationalUnit -Name "{ou_name}" -Path "{provider.naming_context}"

    # Create the standard user
    $pass = ConvertTo-SecureString "{password}" -AsPlainText -Force
    New-ADUser -Name "{user_name}" -SamAccountName "{user_name}" -AccountPassword $pass -Enabled $true -Path "CN=Users,{provider.naming_context}"

    # Get NetBIOS domain name required for dsacls
    $netbios = (Get-ADDomain).NetBIOSName

    # Grant the user Full Control (Generic All) over the OU and everything inside it
    # /I:T ensures the user can modify the computer object's attributes after creation
    dsacls "{ou_dn}" /I:T /G "${{netbios}}\\{user_name}:GA"
    """

    provider.host.conn.run(setup_script)

    client.adcli.join(
        domain=provider.host.domain,
        login_user=user_name,
        password=password,
        args=["--verbose", f"--domain-ou={ou_dn}", f"--domain-controller={provider.host.hostname}"],
        krb=False,
    )

    short_hostname = client.host.hostname.split(".")[0]
    verify_script = f"(Get-ADComputer -Identity '{short_hostname}').DistinguishedName"

    verify_result = provider.host.conn.run(verify_script)
    actual_computer_dn = verify_result.stdout.strip()

    assert (
        ou_dn in actual_computer_dn
    ), f"Computer joined, but was not placed in the delegated OU! Expected it in {ou_dn}, found it at {actual_computer_dn}"


@pytest.mark.importance("medium")
@pytest.mark.topology(KnownTopologyGroup.AnyAD)
def test_adcli_useful_message_on_failure(client: Client, provider: GenericADProvider):
    """
    :title: adcli provides a useful message if command fails
    :steps:
        1. Attempt to join the client to the AD-domain using an intentionally incorrect password.
    :expectedresults:
        1. The adcli join operation fails with a non-zero return code.
        2. The standard error contains a useful, descriptive authentication failure message.
    """
    bad_password = "ThisIsDefinitelyTheWrongPassword123!"

    join_command = client.adcli.join(
        domain=provider.host.domain,
        login_user=provider.host.adminuser,
        args=["--verbose"],
        krb=False,
        password=bad_password,
    )

    assert join_command.rc != 0, "adcli join unexpectedly succeeded with a bad password!"

    error_output = join_command.stderr.lower()
    assert (
        "couldn't authenticate" in error_output or "preauthentication failed" in error_output
    ), f"Expected a useful authentication error message, but got: {join_command.stderr}"
