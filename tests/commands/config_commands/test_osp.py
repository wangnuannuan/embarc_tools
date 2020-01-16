from __future__ import print_function, division
import os
import pytest
import subprocess
from ..conftest import runcmd


def test_bsp_commands(get_bsp):
    runcmd(["config", "bsp", "--list"])
    runcmd(["config", "bsp", "--rename", "new_bsp", "rename"])
    runcmd(["config", "bsp", "--list"])
    runcmd(["config", "bsp", "--rename", "rename", "new_bsp"])
