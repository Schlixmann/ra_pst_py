#!/usr/bin/env python3


import argparse
from src.ra_pst_py.builder import build_rapst

def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(
        description="Command-line interface to create an ra_pst object using build_rapst."
    )
    
    # Add required positional arguments
    parser.add_argument(
        "process_file",
        type=str,
        help="Path to the process file."
    )
    parser.add_argument(
        "resource_file",
        type=str,
        help="Path to the resource file."
    )
    # Add optional output path argument
    parser.add_argument(
        "--output",
        type=str,
        default="ra_pst.xml",
        help="Path to save the resulting ra_pst object (default: './ra_pst.xml')."
    )
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Call the build_rapst function with the arguments
    rapst_object = build_rapst(args.process_file, args.resource_file)

    # Save ra_pst at specified location

    rapst_object.save_ra_pst(args.output)
    
    # You can optionally print or save the resulting object
    print("ra_pst object successfully created:", rapst_object)

if __name__ == "__main__":
    main()