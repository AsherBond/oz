# Copyright (C) 2010,2011  Chris Lalancette <clalance@redhat.com>

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation;
# version 2.1 of the License.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import re
import os
import shutil
import urllib2
import paramiko
import Crypto

import Guest
import ozutil
import OzException

class RedHatCDGuest(Guest.CDGuest):
    def __init__(self, name, distro, update, arch, installtype, nicmodel,
                 clockoffset, mousetype, diskbus, config):
        Guest.CDGuest.__init__(self, name, distro, update, arch, installtype,
                               nicmodel, clockoffset, mousetype, diskbus,
                               config)
        self.sshprivkey = os.path.join('/etc', 'oz', 'id_rsa-icicle-gen')
        self.sshd_config = \
"""SyslogFacility AUTHPRIV
PasswordAuthentication yes
ChallengeResponseAuthentication no
GSSAPIAuthentication yes
GSSAPICleanupCredentials yes
UsePAM yes
AcceptEnv LANG LC_CTYPE LC_NUMERIC LC_TIME LC_COLLATE LC_MONETARY LC_MESSAGES
AcceptEnv LC_PAPER LC_NAME LC_ADDRESS LC_TELEPHONE LC_MEASUREMENT
AcceptEnv LC_IDENTIFICATION LC_ALL LANGUAGE
AcceptEnv XMODIFIERS
X11Forwarding yes
Subsystem	sftp	/usr/libexec/openssh/sftp-server
"""

    def generate_iso(self):
        self.log.debug("Generating new ISO")
        Guest.subprocess_check_output(["mkisofs", "-r", "-T", "-J", "-V",
                                       "Custom", "-b", "isolinux/isolinux.bin",
                                       "-c", "isolinux/boot.cat",
                                       "-no-emul-boot", "-boot-load-size", "4",
                                       "-boot-info-table", "-v", "-v",
                                       "-o", self.output_iso,
                                       self.iso_contents])

    def get_default_runlevel(self, g_handle):
        runlevel = "3"
        if g_handle.exists('/etc/inittab'):
            lines = g_handle.cat('/etc/inittab').split("\n")
            for line in lines:
                if re.match('id:', line):
                    try:
                        runlevel = line.split(':')[1]
                    except:
                        pass
                    break

        return runlevel

    def get_service_runlevel_link(self, g_handle, service):
        runlevel = self.get_default_runlevel(g_handle)

        lines = g_handle.cat('/etc/init.d/' + service).split("\n")
        startlevel = "99"
        for line in lines:
            if re.match('# chkconfig:', line):
                try:
                    startlevel = line.split(':')[1].split()[1]
                except:
                    pass
                break

        return "/etc/rc.d/rc" + runlevel + ".d/S" + startlevel + service

    def image_ssh_teardown_step_1(self, g_handle):
        self.log.debug("Teardown step 1")
        # reset the authorized keys
        self.log.debug("Resetting authorized_keys")
        if g_handle.exists('/root/.ssh'):
            g_handle.rm_rf('/root/.ssh')

        if g_handle.exists('/root/.ssh.icicle'):
            g_handle.mv('/root/.ssh.icicle', '/root/.ssh')

    def image_ssh_teardown_step_2(self, g_handle):
        self.log.debug("Teardown step 2")
        # remove custom sshd_config
        self.log.debug("Resetting sshd_config")
        if g_handle.exists('/etc/ssh/sshd_config'):
            g_handle.rm('/etc/ssh/sshd_config')
        if g_handle.exists('/etc/ssh/sshd_config.icicle'):
            g_handle.mv('/etc/ssh/sshd_config.icicle', '/etc/ssh/sshd_config')

        # reset the service link
        self.log.debug("Resetting sshd service")
        startuplink = self.get_service_runlevel_link(g_handle, 'sshd')
        if g_handle.exists(startuplink):
            g_handle.rm(startuplink)
        if g_handle.exists(startuplink + ".icicle"):
            g_handle.mv(startuplink + ".icicle", startuplink)

    def image_ssh_teardown_step_3(self, g_handle):
        self.log.debug("Teardown step 3")
        # reset iptables
        self.log.debug("Resetting iptables rules")
        if g_handle.exists('/etc/sysconfig/iptables'):
            g_handle.rm('/etc/sysconfig/iptables')
        if g_handle.exists('/etc/sysconfig/iptables.icicle'):
            g_handle.mv('/etc/sysconfig/iptables.icicle',
                        '/etc/sysconfig/iptables')

    def image_ssh_teardown_step_4(self, g_handle):
        self.log.debug("Teardown step 4")
        # remove announce cronjob
        self.log.debug("Resetting announcement to host")
        if g_handle.exists('/etc/cron.d/announce'):
            g_handle.rm('/etc/cron.d/announce')

        # remove icicle-nc binary
        self.log.debug("Removing icicle-nc binary")
        if g_handle.exists('/root/icicle-nc'):
            g_handle.rm('/root/icicle-nc')

        # reset the service link
        self.log.debug("Resetting crond service")
        startuplink = self.get_service_runlevel_link(g_handle, 'crond')
        if g_handle.exists(startuplink):
            g_handle.rm(startuplink)
        if g_handle.exists(startuplink + ".icicle"):
            g_handle.mv(startuplink + ".icicle", startuplink)

    def image_ssh_teardown_step_5(self, g_handle):
        self.log.debug("Teardown step 5")
        if g_handle.exists('/etc/selinux/config'):
            g_handle.rm('/etc/selinux/config')

        if g_handle.exists('/etc/selinux/config.icicle'):
            g_handle.mv('/etc/selinux/config.icicle', '/etc/selinux/config')

    def collect_teardown(self, libvirt_xml):
        self.log.info("Collection Teardown")

        g_handle = self.guestfs_handle_setup(libvirt_xml)

        try:
            self.image_ssh_teardown_step_1(g_handle)

            self.image_ssh_teardown_step_2(g_handle)

            self.image_ssh_teardown_step_3(g_handle)

            self.image_ssh_teardown_step_4(g_handle)

            self.image_ssh_teardown_step_5(g_handle)
        finally:
            self.guestfs_handle_cleanup(g_handle)
            shutil.rmtree(self.icicle_tmp)

    def image_ssh_setup_step_1(self, g_handle):
        # part 1; upload the keys
        self.log.debug("Step 1: Uploading ssh keys")
        if g_handle.exists('/root/.ssh'):
            g_handle.mv('/root/.ssh', '/root/.ssh.icicle')
        g_handle.mkdir('/root/.ssh')

        if g_handle.exists('/root/.ssh/authorized_keys'):
            g_handle.mv('/root/.ssh/authorized_keys',
                        '/root/.ssh/authorized_keys.icicle')

        self.generate_openssh_key(self.sshprivkey)

        g_handle.upload(self.sshprivkey + ".pub", '/root/.ssh/authorized_keys')

    def image_ssh_setup_step_2(self, g_handle):
        # part 2; check and setup sshd
        self.log.debug("Step 2: setup sshd")
        if not g_handle.exists('/etc/init.d/sshd') or not g_handle.exists('/usr/sbin/sshd'):
            raise OzException.OzException("ssh not installed on the image, cannot continue")

        startuplink = self.get_service_runlevel_link(g_handle, 'sshd')
        if g_handle.exists(startuplink):
            g_handle.mv(startuplink, startuplink + ".icicle")
        g_handle.ln_sf('/etc/init.d/sshd', startuplink)

        sshd_config_file = self.icicle_tmp + "/sshd_config"
        f = open(sshd_config_file, 'w')
        f.write(self.sshd_config)
        f.close()

        if g_handle.exists('/etc/ssh/sshd_config'):
            g_handle.mv('/etc/ssh/sshd_config', '/etc/ssh/sshd_config.icicle')
        g_handle.upload(sshd_config_file, '/etc/ssh/sshd_config')
        os.unlink(sshd_config_file)

    def image_ssh_setup_step_3(self, g_handle):
        # part 3; open up iptables
        self.log.debug("Step 3: Open up the firewall")
        if g_handle.exists('/etc/sysconfig/iptables'):
            g_handle.mv('/etc/sysconfig/iptables', '/etc/sysconfig/iptables.icicle')
        # implicit else; if there is no iptables file, the firewall is open

    def image_ssh_setup_step_4(self, g_handle):
        # part 4; make sure the guest announces itself
        self.log.debug("Step 4: Guest announcement")
        if not g_handle.exists('/etc/init.d/crond') or not g_handle.exists('/usr/sbin/crond'):
            raise OzException.OzException("cron not installed on the image, cannot continue")

        iciclepath = ozutil.generate_full_guesttools_path('icicle-nc')
        g_handle.upload(iciclepath, '/root/icicle-nc')
        g_handle.chmod(0755, '/root/icicle-nc')

        announcefile = self.icicle_tmp + "/announce"
        f = open(announcefile, 'w')
        f.write('*/1 * * * * root /bin/bash -c "/root/icicle-nc ' + self.host_bridge_ip + ' ' + str(self.listen_port) + '"\n')
        f.close()

        g_handle.upload(announcefile, '/etc/cron.d/announce')

        startuplink = self.get_service_runlevel_link(g_handle, 'crond')
        if g_handle.exists(startuplink):
            g_handle.mv(startuplink, startuplink + ".icicle")
        g_handle.ln_sf('/etc/init.d/crond', startuplink)

        os.unlink(announcefile)

    def image_ssh_setup_step_5(self, g_handle):
        # part 5; set SELinux to permissive mode so we don't have to deal with
        # incorrect contexts
        self.log.debug("Step 5: Set SELinux to permissive mode")
        if g_handle.exists('/etc/selinux/config'):
            g_handle.mv('/etc/selinux/config', '/etc/selinux/config.icicle')

        selinuxfile = self.icicle_tmp + "/selinux"
        f = open(selinuxfile, 'w')
        f.write("SELINUX=permissive\n")
        f.write("SELINUXTYPE=targeted\n")
        f.close()

        g_handle.upload(selinuxfile, "/etc/selinux/config")

        os.unlink(selinuxfile)

    def collect_setup(self, libvirt_xml):
        self.log.info("Collection Setup")

        self.mkdir_p(self.icicle_tmp)

        g_handle = self.guestfs_handle_setup(libvirt_xml)

        # we have to do 5 things to make sure we can ssh into RHEL/Fedora:
        # 1)  Upload our ssh key
        # 2)  Make sure sshd is running on boot
        # 3)  Make sure that port 22 is open in the firewall
        # 4)  Make the guest announce itself to the host
        # 5)  Set SELinux to permissive mode

        try:
            try:
                self.image_ssh_setup_step_1(g_handle)

                try:
                    self.image_ssh_setup_step_2(g_handle)

                    try:
                        self.image_ssh_setup_step_3(g_handle)

                        try:
                            self.image_ssh_setup_step_4(g_handle)

                            try:
                                self.image_ssh_setup_step_5(g_handle)
                            except:
                                self.image_ssh_teardown_step_5(g_handle)
                                raise
                        except:
                            self.image_ssh_teardown_step_4(g_handle)
                            raise
                    except:
                        self.image_ssh_teardown_step_3(g_handle)
                        raise
                except:
                    self.image_ssh_teardown_step_2(g_handle)
                    raise
            except:
                self.image_ssh_teardown_step_1(g_handle)
                raise

        finally:
            self.guestfs_handle_cleanup(g_handle)

    def guest_execute_command(self, guestaddr, command):
        key = paramiko.RSAKey.from_private_key_file(self.sshprivkey)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.MissingHostKeyPolicy())
        Crypto.Random.atfork()
        ssh.connect(guestaddr, username='root', pkey=key, timeout=5)

        channel = ssh.get_transport().open_session()
        channel.exec_command(command)
        inchan = channel.makefile('wb', -1)
        outchan = channel.makefile('rb', -1)
        errchan = channel.makefile_stderr('rb', -1)
        retcode = channel.recv_exit_status()

        stdout = ''.join(outchan.readlines())
        stderr = ''.join(errchan.readlines())

        ssh.close()

        if retcode:
            raise OzException.OzException("'%s' failed(%d): %s" % (command, retcode, stderr))

        return (stdout, stderr, retcode)

    def do_icicle(self, guestaddr):
        stdout, stderr, retcode = self.guest_execute_command(guestaddr,
                                                             'rpm -qa')

        return self.output_icicle_xml(stdout.split("\n"), self.tdl.description)

    def generate_icicle(self, libvirt_xml):
        self.log.info("Generating ICICLE")

        self.collect_setup(libvirt_xml)

        icicle_output = ''
        libvirt_dom = None
        try:
            libvirt_dom = self.libvirt_conn.createXML(libvirt_xml, 0)

            try:
                guestaddr = None
                guestaddr = self.wait_for_guest_boot()
                icicle_output = self.do_icicle(guestaddr)
            finally:
                self.shutdown_guest(guestaddr, libvirt_dom)

        finally:
            self.collect_teardown(libvirt_xml)

        return icicle_output

    def guest_live_upload(self, guestaddr, source, destination):
        self.guest_execute_command(guestaddr,
                                   "mkdir -p " + os.path.dirname(destination))

        key = paramiko.RSAKey.from_private_key_file(self.sshprivkey)
        transport = paramiko.Transport((guestaddr, 22))
        transport.connect(username='root', pkey=key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(source, destination)
        sftp.close()
        transport.close()

    def customize_files(self, guestaddr):
        self.log.info("Uploading custom files")
        for name, content in self.tdl.files.items():
            localname = os.path.join(self.icicle_tmp, "file")
            f = open(localname, 'w')
            f.write(content)
            f.close()
            self.guest_live_upload(guestaddr, localname, name)
            os.unlink(localname)

    def shutdown_guest(self, guestaddr, libvirt_dom):
        if guestaddr is not None:
            try:
                self.guest_execute_command(guestaddr, 'shutdown -h now')
                if not self.wait_for_guest_shutdown(libvirt_dom):
                    self.log.warn("Guest did not shutdown in time, going to kill")
                else:
                    libvirt_dom = None
            except:
                self.log.warn("Failed shutting down guest, forcibly killing")

        if libvirt_dom is not None:
            libvirt_dom.destroy()

    def generate_install_media(self, force_download=False):
        self.log.info("Generating install media")

        if not force_download and os.access(self.modified_iso_cache, os.F_OK):
            self.log.info("Using cached modified media")
            shutil.copyfile(self.modified_iso_cache, self.output_iso)
            return

        fetchurl = self.url
        if self.tdl.installtype == 'url':
            fetchurl += "/images/boot.iso"

        self.get_original_iso(fetchurl, force_download)
        self.copy_iso()
        try:
            if hasattr(self, 'check_dvd') and self.tdl.installtype == 'iso':
                self.check_dvd()
            self.modify_iso()
            self.generate_iso()
            if self.cache_modified_media:
                self.log.info("Caching modified media for future use")
                shutil.copyfile(self.output_iso, self.modified_iso_cache)
        finally:
            self.cleanup_iso()

class RedHatCDYumGuest(RedHatCDGuest):
    def check_anaconda_url(self, tdl, iso=True, url=True):
        url = self.check_url(tdl, iso, url)

        if self.tdl.installtype == 'url':
            # The HTTP/1.1 specification allows for servers that don't support
            # byte ranges; if the client requests it and the server doesn't
            # support it, it is supposed to return a header that looks like:
            #
            #   Accept-Ranges: none
            #
            # You can see this in action by editing httpd.conf:
            #
            #   ...
            #   LoadModule headers_module
            #   ...
            #   Header set Accept-Ranges "none"
            #
            # and then trying to fetch a file with wget:
            #
            #   wget --header="Range: bytes=5-10" http://path/to/my/file
            #
            # Unfortunately, anaconda does not honor this server header, and
            # blindly requests a byte range anyway.  When this happens, the
            # server throws a "403 Forbidden", and the URL install fails.
            #
            # There is the additional problem of mirror lists.  If we take
            # the original URL that was given to us, and it happens to be
            # a redirect, then what can happen is that each individual package
            # during the install can come from a different mirror (some of
            # which may not support the byte ranges).  To avoid both of these
            # problems, resolve the (possible) redirect to a real mirror, and
            # check if we hit a server that doesn't support ranges.  If we do
            # hit one of these, try up to 5 times to redirect to a different
            # mirror.  If after this we still cannot find a server that
            # supports byte ranges, fail.
            count = 5
            while count > 0:
                response = urllib2.urlopen(url)
                info = response.info()
                new_url = response.geturl()
                response.close()

                self.log.debug("Original URL %s resolved to %s" % (url, new_url))

                if 'Accept-Ranges' in info and info['Accept-Ranges'] == "none":
                    if url == new_url:
                        # optimization; if the URL we resolved to is exactly
                        # the same as what we started with, this is *not*
                        # a redirect, and we should fail immediately
                        count = 0
                        break

                    count -= 1
                    continue

                url = new_url
                break

            if count == 0:
                raise OzException.OzException("%s URL installs cannot be done using servers that don't accept byte ranges.  Please try another mirror" % (tdl.distro))

        return url

    def customize_repos(self, guestaddr):
        self.log.debug("Installing additional repository files")
        for repo in self.tdl.repositories.values():
            filename = repo.name + ".repo"
            localname = os.path.join(self.icicle_tmp, filename)
            f = open(localname, 'w')
            f.write("[%s]\n" % repo.name)
            f.write("name=%s\n" % repo.name)
            f.write("baseurl=%s\n" % repo.url)
            f.write("enabled=1\n")
            if repo.signed:
                f.write("gpgcheck=1\n")
            else:
                f.write("gpgcheck=0\n")
            f.close()

            self.guest_live_upload(guestaddr, localname,
                                   "/etc/yum.repos.d/" + filename)

            os.unlink(localname)

    def do_customize(self, guestaddr):
        self.customize_repos(guestaddr)

        self.log.debug("Installing custom packages")
        packstr = ''
        for package in self.tdl.packages:
            packstr += package.name + ' '

        if packstr != '':
            self.guest_execute_command(guestaddr,
                                       'yum -y install %s' % (packstr))

        self.customize_files(guestaddr)

        self.log.debug("Syncing")
        self.guest_execute_command(guestaddr, 'sync')

    def customize(self, libvirt_xml):
        self.log.info("Customizing image")

        if not self.tdl.packages and not self.tdl.files:
            self.log.info("No additional packages or files to install, skipping customization")
            return

        self.collect_setup(libvirt_xml)

        libvirt_dom = None
        try:
            libvirt_dom = self.libvirt_conn.createXML(libvirt_xml, 0)

            try:
                guestaddr = None
                guestaddr = self.wait_for_guest_boot()

                self.do_customize(guestaddr)
            finally:
                self.shutdown_guest(guestaddr, libvirt_dom)
        finally:
            self.collect_teardown(libvirt_xml)

    def customize_and_generate_icicle(self, libvirt_xml):
        self.log.info("Customizing and generating ICICLE")

        self.collect_setup(libvirt_xml)

        libvirt_dom = None
        try:
            libvirt_dom = self.libvirt_conn.createXML(libvirt_xml, 0)

            try:
                guestaddr = self.wait_for_guest_boot()

                if self.tdl.packages or self.tdl.files:
                    self.do_customize(guestaddr)

                icicle = self.do_icicle(guestaddr)
            finally:
                self.shutdown_guest(guestaddr, libvirt_dom)
        finally:
            self.collect_teardown(libvirt_xml)

        return icicle

class RedHatFDGuest(Guest.FDGuest):
    def __init__(self, tdl, config, auto, ks_name, nicmodel):
        self.tdl = tdl
        if self.tdl.arch != "i386":
            raise OzException.OzException("Invalid arch " + self.tdl.arch + "for " + self.tdl.distro + " guest")

        self.url = self.check_url(self.tdl, iso=False, url=True)

        self.ks_file = auto
        if self.ks_file is None:
            self.ks_file = ozutil.generate_full_auto_path(ks_name)

        Guest.FDGuest.__init__(self, self.tdl.name, self.tdl.distro,
                               self.tdl.update, self.tdl.arch, nicmodel, None,
                               None, None, config)

    def modify_floppy(self):
        self.mkdir_p(self.floppy_contents)

        self.log.debug("Putting the kickstart in place")

        output_ks = os.path.join(self.floppy_contents, "ks.cfg")
        infile = open(self.ks_file, 'r')
        outfile = open(output_ks, 'w')

        for line in infile.xreadlines():
            if re.match("^url", line):
                outfile.write("url --url " + self.url + "\n")
            else:
                outfile.write(line)

        infile.close()
        outfile.close()

        Guest.subprocess_check_output(["mcopy", "-i", self.output_floppy,
                                       output_ks, "::KS.CFG"])

        self.log.debug("Modifying the syslinux.cfg")

        syslinux = os.path.join(self.floppy_contents, "SYSLINUX.CFG")
        outfile = open(syslinux, "w")
        outfile.write("default customboot\n")
        outfile.write("prompt 1\n")
        outfile.write("timeout 1\n")
        outfile.write("label customboot\n")
        outfile.write("  kernel vmlinuz\n")
        outfile.write("  append initrd=initrd.img lang= devfs=nomount ramdisk_size=9216 ks=floppy method=" + self.url + "\n")
        outfile.close()

        # sometimes, syslinux.cfg on the floppy gets marked read-only.  Avoid
        # problems with the subsequent mcopy by marking it read/write.
        Guest.subprocess_check_output(["mattrib", "-r", "-i",
                                       self.output_floppy, "::SYSLINUX.CFG"])

        Guest.subprocess_check_output(["mcopy", "-n", "-o", "-i",
                                       self.output_floppy, syslinux,
                                       "::SYSLINUX.CFG"])

    def generate_install_media(self, force_download=False):
        self.log.info("Generating install media")

        if not force_download and os.access(self.modified_floppy_cache,
                                            os.F_OK):
            self.log.info("Using cached modified media")
            shutil.copyfile(self.modified_floppy_cache, self.output_floppy)
            return

        self.get_original_floppy(self.url + "/images/bootnet.img",
                                 force_download)
        self.copy_floppy()
        try:
            self.modify_floppy()
            if self.cache_modified_media:
                self.log.info("Caching modified media for future use")
                shutil.copyfile(self.output_floppy, self.modified_floppy_cache)
        finally:
            self.cleanup_floppy()
