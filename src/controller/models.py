class Input_error(Exception):
    """
    Exception raised for errors in the input.
    """
    pass

class Forbidden_error(Exception):
    """
    Exception raised for forbidden actions due to policy.
    """
    pass

class Internal_error(Exception):
    """
    Exception raised for errors 500.
    """
    pass

class Conflict_error(Exception):
    """
    Exception raised for errors 409.
    """
    pass

class IsInUse_error(Exception):
    """
    Exception raised for errors 403 or 423.
    """
    pass

class NotFound_error(Exception):
    """
    Exception raised for errors 404.
    """
    pass
