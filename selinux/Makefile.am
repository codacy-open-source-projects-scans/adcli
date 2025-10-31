include $(top_srcdir)/Makefile.decl

SELINUXTYPE = targeted

if BUILD_SELINUX_POLICY
MODULE = adcli.pp
else
MODULE =
endif

dist_noinst_DATA = \
	adcli.fc \
	adcli.te \
	$(NULL)

selinuxpolicydir = $(datarootdir)/selinux/packages/$(SELINUXTYPE)
selinuxpolicy_DATA = \
	$(MODULE) \
	$(NULL)

adcli.pp: adcli.fc adcli.te
	make VPATH=$(VPATH) -f $(SELINUX_MAKEFILE) $@

CLEANFILES = \
	adcli.pp \
	adcli.if \
	$(NULL)

clean-local:
	rm -rf tmp/
