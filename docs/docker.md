# Docker images

### Default image

To build a default `ipybox` Docker image with tag `ghcr.io/gradion-ai/ipybox:latest` and minimal dependencies, run:

```bash
uvx ipybox build
```

Alternatively, if you have `ipybox` installed as a Python package, you can run:

```bash
python -m ipybox build
```

Containers of this image will run with the same user and group IDs as the user who built the image. To create a container running as `root`, use the `-r` or `--root` option:

```bash
uvx ipybox build --r
```

To see all command line options, run:

```bash
uvx ipybox --help
```

!!! Hint "Prebuilt image"

    Run `docker pull ghcr.io/gradion-ai/ipybox` to get a prebuilt Docker image built with the `-r` option.

### Custom image

To build a custom `ipybox` Docker image with additional Python packages preinstalled, create a `dependencies.txt` file that follows the [PEP 631](https://peps.python.org/pep-0631/) dependency specification format. For example:

```txt title="dependencies.txt"
"pandas>=2.2,<3",
"scikit-learn>=1.5,<2",
"matplotlib>=3.9,<4"
```

Then build the image by referencing the `dependencies.txt` file and optionally providing a custom tag:

```bash
uvx ipybox build -d dependencies.txt -t gradion-ai/ipybox-custom:v1
```

Code executed in containers of the custom `gradion-ai/ipybox-custom:v1` image can now import these packages.

!!! tip

    You can also [install packages at runtime](examples.md#install-packages-at-runtime).
