#!/usr/bin/env bash

mkdir setup_temp
cd setup_temp

check_linux_package () {
    echo "Checking if $1 is installed..."
    check1=false
    check2=false
    if dpkg --get-selections | grep -q "$1"; then check1=true; fi
    if command -v "$1" > /dev/null 2>&1; then check2=true; fi
    if [ $check1 = true ] || [ $check2 = true ]; then
        echo "$1 OK."
    else
        echo "$1 is not installed. Attempting to install (Ubuntu)..."
        sudo apt-get --assume-yes install $1 > /dev/null 2>&1
        if [ $? -eq 0 ]; then 
            echo "$1 OK."
        else
            echo "Installation failed. Aborting..."
            exit 1
        fi
    fi
}

check_tkinter () {
    echo "Checking if tkinter is installed..."

    python3 -c "import tkinter" > /dev/null 2>&1
    if [ $? -eq 0 ]; then 
        echo "tkinter OK."
    else
        echo "tkinter is not installed. Attempting to install (Ubuntu)..."
        sudo apt-get --assume-yes install python3-tk > /dev/null 2>&1
        if [ $? -eq 0 ]; then 
            echo "tkinter OK."
        else
            echo "Installation failed. Aborting..."
            exit 1
        fi
    fi
}

check_python_module () {
    echo "Checking if $1 is installed..."
    python3 -c "import $1" > /dev/null 2>&1
    if [ $? -eq 0 ]; then 
        echo "$1 OK."
    else
        pip3 install $1 > /dev/null 2>&1
        if [ $? -eq 0 ]; then 
            echo "Installed $1."
        else
            echo "Installation failed. Aborting..."
            exit 1
        fi
    fi
    echo "Checking that $1 is working..."
    python3 -c "import $1" > /dev/null 2>&1
    if [ $? -eq 0 ]; then 
        echo "$1 OK."
    elif [ "$1" = "pygit2" ]; then
        sudo ldconfig > /dev/null 2>&1
        python3 -c "import $1" > /dev/null 2>&1
        if [ $? -eq 0 ]; then 
            echo "$1 OK."
        else
            echo "$1 not working. Aborting..."
            echo "Please refer to $2 for installation details."
            exit 1
        fi
    else
        echo "$1 not working. Aborting..."
        echo "Please refer to $2 for installation details."
        exit 1
    fi
}

##### Main setup script #####

check_linux_package python3
check_linux_package pip3
check_linux_package git
check_linux_package cmake
check_linux_package openssl
check_linux_package libgit2-dev
# check_linux_package autoconf
# check_linux_package pkg-config
# check_linux_package checkinstall
check_linux_package ctags

check_tkinter

# echo "Checking if libgit2 is installed..."
# if ! [ -f /usr/local/lib/libgit2.so ]; then
#     echo "libgit2 is not installed. Attempting to install (Ubuntu)..."
#     wget https://github.com/libgit2/libgit2/archive/v0.27.0.tar.gz > /dev/null 2>&1
#     tar xzf v0.27.0.tar.gz
#     cd libgit2-0.27.0/
#     cmake .
#     make
#     sudo make install
# else
#     echo "libgit2 OK."
# fi

check_python_module pygit2 http://www.pygit2.org/install.html
check_python_module matplotlib https://matplotlib.org/users/installing.html
check_python_module termcolor https://pypi.org/project/termcolor/

cd ..
rm -rf setup_temp
echo "Setup finished."