#!/usr/bin/env python3
"""CDK app entry point."""

import aws_cdk as cdk

from stacks.inkvault_stack import InkVaultStack

app = cdk.App()
InkVaultStack(app, "InkVaultStack")
app.synth()
