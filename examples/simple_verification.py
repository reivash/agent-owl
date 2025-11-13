"""
Simple Verification Plugin Template for Agent Owl

This is a minimal example showing how to create custom verification logic.
"""


def verify():
    """
    Verify application state

    Returns:
        tuple: (status, message, prompt_override)
            - status: str identifier used to select prompt from config
            - message: str description logged to console
            - prompt_override: str or None - if provided, overrides config prompts

    Example returns:
        ('ready', 'Application ready', None)
        ('error', 'Application crashed', 'Please restart the application')
    """

    # Add your custom verification logic here
    # Examples:
    # - Check if a process is running
    # - Read log files for errors
    # - Check database connectivity
    # - Verify API endpoints are responding
    # - Monitor system resources

    # For this simple example, always return ready status
    return 'default', 'No custom verification configured', None
