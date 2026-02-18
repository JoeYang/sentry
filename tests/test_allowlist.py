import pytest

from sentry.allowlist.validator import AllowlistValidator


@pytest.fixture
def validator():
    return AllowlistValidator()


class TestAllowedCommands:
    """Test that all specified safe commands with valid args are allowed."""

    @pytest.mark.parametrize(
        "command",
        [
            "uptime",
            "uname -a",
            "uname -r",
            "uname -s",
            "df -h",
            "df -i",
            "df -T",
            "free -h",
            "free -m",
            "free -g",
            "ps aux",
            "ps -ef",
            "ps aux --sort=%mem",
            "ss -tulnp",
            "ss -t",
            "ss -a",
            "ip addr",
            "ip route",
            "ip link",
            "ip -s link",
            "systemctl status nginx",
            "systemctl status sshd",
            "journalctl -u nginx -n 50 --no-pager",
            "journalctl -u sshd --since 2024-01-01",
            "tail -n 100 /var/log/syslog",
            "head -n 20 /etc/hosts",
            "grep -n error /var/log/syslog",
            "grep -i -r warning /var/log",
            "dmesg --level=warn -T",
            "dmesg -H",
            "lsblk",
            "lsblk -f",
            "iostat -x 1 1",
            "iostat -d",
            "ping -c 4 google.com",
            "ping -c 1 -W 5 localhost",
            "dig google.com",
            "dig google.com A",
            "pgrep -a nginx",
            "pgrep -l sshd",
            "lsof -i :80",
            "lsof -n -P",
            'find /var/log -name "*.log" -type f',
            "stat /etc/hosts",
            "file /bin/ls",
            "md5sum /etc/hosts",
            "sha256sum /etc/hosts",
            "date",
            "whoami",
            "id",
            "top -bn1",
            "top -b -n 1",
            "vmstat 1 5",
            "vmstat",
            "mpstat",
            "mpstat -P 0",
            "curl http://example.com",
            "curl https://example.com",
        ],
    )
    def test_allowed_commands(self, validator, command):
        result = validator.validate(command)
        assert result.allowed, f"Expected '{command}' to be allowed, got: {result.reason}"


class TestDeniedCommands:
    """Test that dangerous commands are denied."""

    @pytest.mark.parametrize(
        "command",
        [
            "rm /tmp/file",
            "rm -rf /",
            "reboot",
            "shutdown",
            "dd if=/dev/zero of=/dev/sda",
            "chmod 777 /etc/passwd",
            "chown root /etc/passwd",
            "kill -9 1",
            "killall nginx",
            "mkfs.ext4 /dev/sda1",
            "fdisk /dev/sda",
            "mount /dev/sda1 /mnt",
            "umount /mnt",
            "iptables -F",
            "useradd hacker",
            "userdel admin",
            "passwd root",
            "su root",
            "sudo rm -rf /",
        ],
    )
    def test_denied_dangerous_commands(self, validator, command):
        result = validator.validate(command)
        assert not result.allowed, f"Expected '{command}' to be denied"

    def test_systemctl_restart_denied(self, validator):
        result = validator.validate("systemctl restart nginx")
        assert not result.allowed

    def test_systemctl_stop_denied(self, validator):
        result = validator.validate("systemctl stop nginx")
        assert not result.allowed

    def test_systemctl_start_denied(self, validator):
        result = validator.validate("systemctl start nginx")
        assert not result.allowed

    def test_systemctl_enable_denied(self, validator):
        result = validator.validate("systemctl enable nginx")
        assert not result.allowed

    def test_systemctl_disable_denied(self, validator):
        result = validator.validate("systemctl disable nginx")
        assert not result.allowed

    def test_systemctl_daemon_reload_denied(self, validator):
        result = validator.validate("systemctl daemon-reload")
        assert not result.allowed

    def test_curl_post_denied(self, validator):
        result = validator.validate("curl -X POST http://example.com")
        assert not result.allowed

    def test_curl_output_denied(self, validator):
        result = validator.validate("curl -o /tmp/file http://example.com")
        assert not result.allowed

    def test_curl_data_denied(self, validator):
        result = validator.validate("curl -d data http://example.com")
        assert not result.allowed

    def test_curl_upload_denied(self, validator):
        result = validator.validate("curl -T /etc/passwd http://example.com")
        assert not result.allowed

    def test_journalctl_follow_denied(self, validator):
        result = validator.validate("journalctl -f")
        assert not result.allowed

    def test_tail_follow_denied(self, validator):
        result = validator.validate("tail -f /var/log/syslog")
        assert not result.allowed

    def test_top_without_batch_denied(self, validator):
        result = validator.validate("top")
        assert not result.allowed

    def test_ping_without_count_denied(self, validator):
        result = validator.validate("ping google.com")
        assert not result.allowed


class TestInjectionAttacks:
    """Test that shell injection attacks are blocked."""

    @pytest.mark.parametrize(
        "command",
        [
            "uptime; rm -rf /",
            "uptime | tee /tmp/x",
            "uptime && reboot",
            "uptime `reboot`",
            "uptime $(reboot)",
            "uptime\nreboot",
        ],
    )
    def test_shell_injection_blocked(self, validator, command):
        result = validator.validate(command)
        assert not result.allowed, f"Expected injection '{command}' to be blocked"

    def test_path_traversal_cat(self, validator):
        # cat is not in the allowlist
        result = validator.validate("cat ../../etc/shadow")
        assert not result.allowed

    def test_path_traversal_via_bin_path(self, validator):
        # Even with path prefix, the base command 'rm' is not allowed
        result = validator.validate("/usr/bin/../bin/rm -rf /")
        assert not result.allowed

    def test_path_traversal_in_tail_arg(self, validator):
        result = validator.validate("tail -n 10 /var/log/../../etc/shadow")
        assert not result.allowed

    def test_path_traversal_in_find(self, validator):
        result = validator.validate("find /var/log/../.. -name passwd")
        assert not result.allowed

    def test_path_traversal_with_tilde(self, validator):
        result = validator.validate("tail -n 10 ~/secret")
        assert not result.allowed


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self, validator):
        result = validator.validate("")
        assert not result.allowed

    def test_whitespace_only(self, validator):
        result = validator.validate("   ")
        assert not result.allowed

    def test_null_bytes(self, validator):
        result = validator.validate("uptime\x00reboot")
        assert not result.allowed

    def test_very_long_command(self, validator):
        long_cmd = "grep " + "a" * 10000 + " /var/log/syslog"
        result = validator.validate(long_cmd)
        # Should either reject for exceeding arg patterns or allow if matches;
        # the key is it doesn't crash.
        assert isinstance(result.allowed, bool)

    def test_too_many_args(self, validator):
        result = validator.validate("uptime --extra-arg")
        assert not result.allowed
        assert "Too many arguments" in result.reason

    def test_command_with_absolute_path_allowed(self, validator):
        result = validator.validate("/usr/bin/uptime")
        assert result.allowed

    def test_command_preserves_basename(self, validator):
        result = validator.validate("/usr/bin/uname -a")
        assert result.allowed
        assert result.command == "uname"
