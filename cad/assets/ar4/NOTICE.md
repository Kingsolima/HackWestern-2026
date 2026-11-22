# AR4 link meshes

The `*.STL` files in this folder are the Annin Robotics AR4 (MK3) link meshes, copied
unchanged from `annin_ar4_description/meshes/ar4_mk3/` in
[ycheng517/ar4_ros_driver](https://github.com/ycheng517/ar4_ros_driver) at commit
`4b88db1c924515f7ce343105d46a637ecf2d7659`.

That repository is under the MIT License (Copyright (c) 2021 Dexter Ong). The geometry
comes from the AR4 robot designed by Chris Annin / [Annin Robotics](https://www.anninrobotics.com).
We use it to render the arm in a non-commercial hackathon demo and credit both here.

`cad_worker/ar4_meshes.py` poses the links with the joint origins from the same repository's
`urdf/ar_macro.xacro` and removes the J2 motor modelled in `link_1`, so the generated J2 drive
is the only one in the scene.

MIT License text (from the source repository):

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software
> and associated documentation files (the "Software"), to deal in the Software without
> restriction, including without limitation the rights to use, copy, modify, merge, publish,
> distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
> Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
> BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
> DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
