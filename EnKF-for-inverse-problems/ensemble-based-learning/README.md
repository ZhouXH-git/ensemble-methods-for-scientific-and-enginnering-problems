# ensemble based learning

Requires OpenFOAM v1912, [DAFI](https://github.com/xiaoh/DAFI), and [Data Driven Turbulence Modeling](https://github.com/cmichelenstrofer/Data-Driven-Turbulence-Modeling). Follow the steps below to configure the environment.

### OpenFOAM installation
- Follow steps in [OF1912 Install](https://www.cemf.ir/how-to-install-openfoam-v1912-from-source-pack/)
- After installation, source the OpenFOAM 1912 by adding the following line in your `~/.bashrc` file:
  ```bash
  alias of1912 = "source $HOME/OpenFOAM/OpenFOAM-v1912/etc/bashrc"
  ```

### DAFI installation
- Source DAFI init file by adding following line in your `~/.bashrc` file:
  ```bash
  source $HOME/ensemble-based-learning/code/DAFI/init_dafi
  ```

### TensorFlow setup
- Install TensorFlow for C, see [TensorFlow for C](https://tensorflow.google.cn/install/lang_c#linux)
- Install TensorFlow:
  ```bash
  pip install --upgrade tensorflow
  pip install tensorflow-cpu
  ```

### Data-driven turbulence modeling (DDTM) setup
*Notice*: Turbulence models in OpenFOAM are templated and therefore you cannot compile (new) turbulence models individually. Instead,
we can make a local copy of the entire TurbulenceModels directory from OpenFOAM and add the (new) turbulence models therein.
- Make a user copy of TurbulenceModels directory and compile it
  ```bash
  # source OpenFOAM 1912
  of1912
  
  # create the user directory
  mkdir $WM_PROJECT_USER_DIR
  
  # copy TurbulenceModels to user directory
  cd $WM_PROJECT_DIR
  cp -r --parents src/TurbulenceModels $WM_PROJECT_USER_DIR
  
  # change the location of the compiled files in all Make/files
  cd $WM_PROJECT_USER_DIR/src/TurbulenceModels
  sed -i s/FOAM_LIBBIN/FOAM_USER_LIBBIN/g ./*/Make/files
  
  # compile 
  ./Allwmake
  ```
- Copy (new) turbulence model and include it in the compile list
  ```bash
  # copy the new turbulence models
  cp -r $DDTM/code/foam/TurbulenceModels/nonlinear incompressible/turbulentTransportModels/RAS
  
  # manually add the new model to the compile list
  # add the following line to the file 'incompressible/Make/files', using kOmegaQuadratic for ASJ case for example:
  turbulentTransportModels/RAS/nonlinear/kOmegaQuadratic/kOmegaQuadratic.C
  ```
  List of non-linear models: neural network + read g1 - g4 files
  - **kOmegaQuadratic**: quadratic k-omega for training, reads fixed 'g1'-'g4' files
  
  If you want to develop new or modify these turbulence models, be cautious about the ".C" and ".h" files!

- Re-make the turbulence models
  ```bash
  # wmakeLnInclude: create an lnInclude directory for the available turbulence models
  wmakeLnInclude -u turbulenceModels

  # compile again
  ./Allwmake
  ```
Once you setup the above environment, you will be able to run the Axisymmetric Subsonic Jet (ASJ) case!
  
