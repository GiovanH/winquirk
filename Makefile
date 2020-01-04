PYTHON=py -3.7

exec_targets=\
	quirk.exe

all: exe

clean:
	$(RM) -r __pycache__
	$(RM) -r build
	$(RM) -r dist/
	$(RM) -r litedist/

exe: $(addprefix bin/,${exec_targets})

bin/%.exe: %.py
	${PYTHON} -m PyInstaller \
		--onefile \
		--console \
		--distpath ../bin \
		--workpath build \
		--specpath build \
		--name $(notdir $@) \
		$<

.PHONY: all clean exe doc mods