---
title:  "SDN environment setup"
date:   2016-12-19 13:04:23
categories: [sdn]
tags: [sdn]
---

*The following environment setup requires fresh Ubuntu 14.04.1*
### Install Java and OpenDaylight
- Update system:

    ```sh
    sudo apt-get update && sudo apt-get dist-upgrade -y
    ```

- Install Java and configure environment variable (choose one of the following versions):
 - Open JDK:
    ```sh
    sudo apt-get update
    sudo apt-get install openjdk-7-jdk
    sudo echo "JAVA_HOME=\"/usr/lib/jvm/java-7-openjdk-amd64\"" >> /etc/environment
    echo "export JAVA_HOME=\"/usr/lib/jvm/java-7-openjdk-amd64\"" >> ~/.bashrc
    source /etc/environment
    source ~/.bashrc
    ```

 - Java Oracle
    ```sh
    # add repository
    sudo apt-get install python-software-properties -y
    sudo add-apt-repository ppa:webupd8team/java
    sudo apt-get update

    # install java 8
    sudo apt-get install oracle-java8-installer -y
    sudo echo "JAVA_HOME=\"/usr/lib/jvm/java-8-oracle\"" >> /etc/environment
    echo "export JAVA_HOME=\"/usr/lib/jvm/java-8-oracle\"" >> ~/.bashrc
    # 3 following steps for java 7
    # sudo apt-get install oracle-java7-installer -y
    # sudo echo "JAVA_HOME=\"/usr/lib/jvm/java-7-oracle\"" >> /etc/environment
    # echo "export JAVA_HOME=\"/usr/lib/jvm/java-7-oracle\"" >> ~/.bashrc
    source /etc/environment
    source ~/.bashrc
    ```

- Download [OpenDaylight Beryllium SR4](https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/distribution-karaf/0.4.4-Beryllium-SR4/distribution-karaf-0.4.4-Beryllium-SR4.zip):

    ```sh
    wget -c https://nexus.opendaylight.org/content/repositories/opendaylight.release/org/opendaylight/integration/distribution-karaf/0.4.4-Beryllium-SR4/distribution-karaf-0.4.4-Beryllium-SR4.zip
    ```

    To be more convenient, you can also download this file from sdn-course repo.

- Extract *.zip file and run controller:

    ```sh
    unzip distribution-karaf-0.4.4-Beryllium-SR4.zip
    cd distribution-karaf-0.4.4-Beryllium-SR4
    ./bin/karaf
    ```

    OpenDaylight console will look like this:
    <img src="http://i.imgur.com/woPrDLN.png">

- On the OpenDaylight console, install basic features:
    ```sh
    feature:install odl-restconf odl-l2switch-switch odl-mdsal-apidocs odl-dlux-all
    ```

### Install Open vSwitch
- Configure kernel (prevent kernel from upgrading):
  ```sh
  wget -c https://raw.githubusercontent.com/thaihust/sdn-course-material/master/env-setup/kernel-cfg.sh
  chmod +x kernel-cfg.sh
  sudo ./kernel-cfg.sh
  ```

- Install Open vSwitch:

  ```sh
  sudo -i
  wget -c https://raw.githubusercontent.com/pritesh/ovs/nsh-v8/third-party/start-ovs-deb.sh
  chmod +x start-ovs-deb.sh
  ./start-ovs-deb.sh
  ```

### Install mininet (included pox, openvswitch if not exists before)
Choose one of the following options:

- #### Option 1: Mininet VM Installation
 - Download the [Mininet VM image](https://github.com/mininet/mininet/wiki/Mininet-VM-Images) (This VM includes Mininet itself, all OpenFlow binaries and tools pre-installed)

 - Install a virtualization system (Virtualbox or VMWare Workstation).

 - Import Mininet image to Virtualbox or VMWare Workstation and get started.

- #### Option 2: Native Installation from Source
 - Execute the following commands:

    ```sh
    sudo apt-get update
    sudo apt-get install git -y
    git clone git://github.com/mininet/mininet
    cd mininet
    git tag  # list available versions
    git checkout -b 2.2.1 2.2.1  # or whatever version you wish to install
    cd ..
    mininet/util/install.sh -a
    ```
