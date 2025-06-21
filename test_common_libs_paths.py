#!/usr/bin/env python3
"""
Test script to verify path calculations for common_libraries directory
based on different Lambda locations in the directory structure.
"""
import os
from pathlib import Path

def test_path_calculations():
    """Test path calculations for different Lambda locations"""
    
    # Define test cases: Lambda location relative to project root
    test_cases = [
        "lambdas/simple_lambda",                                    # 1 level deep
        "lambdas/api/users",                                       # 2 levels deep  
        "lambdas/api/integrations/post_integrations",              # 3 levels deep
        "lambdas/api/category/subcategory/deep_lambda",            # 4 levels deep
        "lambdas/deeply/nested/structure/example/function",       # 5 levels deep
    ]
    
    # Expected number of "../" needed to reach lambdas/ from each location
    expected_back_steps = [1, 2, 3, 4, 5]
    
    print("Testing path calculations for common_libraries:\n")
    
    for i, lambda_path in enumerate(test_cases):
        back_steps = expected_back_steps[i]
        
        # Calculate the path to common_libraries
        relative_path = "../" * back_steps + "common_libraries"
        
        print(f"Lambda location: {lambda_path}")
        print(f"  Back steps needed: {back_steps}")
        print(f"  Relative path: {relative_path}")
        
        # Verify the calculation
        lambda_dir = Path(lambda_path)
        common_libs_path = lambda_dir / (".." * back_steps) / "common_libraries"
        resolved_path = common_libs_path.resolve()
        
        print(f"  Resolved path: {resolved_path}")
        print(f"  Expected: {Path('lambdas/common_libraries').resolve()}")
        print(f"  Match: {resolved_path == Path('lambdas/common_libraries').resolve()}")
        print()

if __name__ == "__main__":
    test_path_calculations() 