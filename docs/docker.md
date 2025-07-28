# Docker images

You can either use one of the [prebuilt](https://gradion-ai.github.io/freeact/environment/#prebuilt-docker-images) `ipybox` Docker images provided by [`freeact`](https://gradion-ai.github.io/freeact/) or build your own image with [default](#default-image) or [custom](#custom-image) dependencies.

### Default image

To build a default `ipybox` Docker image with name `gradion-ai/ipybox` and minimal dependencies, run:

```bash
python -m ipybox build
```

### Custom image

To build a custom `ipybox` Docker image with additional Python packages preinstalled, create a `dependencies.txt` file that follows the [PEP 631](https://peps.python.org/pep-0631/) dependency specification format. For example:

```txt title="dependencies.txt"
"pandas>=2.2,<3",
"scikit-learn>=1.5,<2",
"matplotlib>=3.9,<4"
```

Then build the image by referencing the `dependencies.txt` file and optionally providing a custom tag:

```bash
python -m ipybox build -d dependencies.txt -t gradion-ai/ipybox-custom:v1
```

Code executed in containers of the custom `gradion-ai/ipybox-custom:v1` image can now import these packages.

!!! note

    Containers created from images that have been built without the `-r` or `--root` option will run with the same user and group IDs as the user who built the image. With the `-r` or `--root` option, containers will run as `root`.

!!! tip

    You can also [install packages at runtime](usage.md#install-packages-at-runtime).
