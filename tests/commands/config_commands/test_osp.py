from __future__ import print_function, division
import os
import pytest
import subprocess
from ..conftest import runcmd


def test_bsp_commands(get_bsp):
    runcmd(["config", "embarc-root", "--list"])
    runcmd(["config", "embarc-root", "--rename", "new_bsp", "rename"])
    runcmd(["config", "embarc-root", "--list"])
    runcmd(["config", "embarc-root", "--rename", "rename", "new_bsp"])
