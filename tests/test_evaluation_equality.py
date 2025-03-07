from lxml import etree
import unittest
import json
import copy
import os
from pathlib import Path

class EvaluationTest(unittest.TestCase):
    def test_equality_of_release_times(self):
        # Test that release times in all online files are same
        directory = Path("testsets_online_final_decomp")
        subfolder = "evaluation"
        
        for folder in sorted(directory.iterdir()):
            sub_path = folder / subfolder
            comparison_dict = {}
            for solution_method in sub_path.iterdir():
                file_list = list(solution_method.glob("*.json"))
                for file_name in file_list:
                    if file_name.name not in comparison_dict.keys():
                       comparison_dict[file_name.name] = {}
                    
                    # open evaluation file:
                    with open(file_name, "r") as f:
                        data = json.load(f)
                    comparison_dict[file_name.name][solution_method.name] = data["metadata"]["release_times"]
            
            for key, data in comparison_dict.items():
                release_times_list = [release_times for key, release_times in data.items()]
                print(release_times_list)
                flag = all(lst == release_times_list[0] for lst in release_times_list) if release_times_list else True
                self.assertEqual(flag, True, f"{release_times_list}")
    
    def test_equality_of_ra_pst(self):
        # Test that release times in all online files are same
        directory = Path("testsets_online_final_decomp")
        subfolder = "evaluation"
        
        folder_random = [folder for folder in directory.iterdir() if "random" in folder.name]
        for folder in folder_random:
            sub_path = folder / subfolder
            comparison_dict = {}
            for solution_method in sub_path.iterdir():
                file_list = list(solution_method.glob("*.json"))
                for file_name in file_list:
                    if file_name.name not in comparison_dict.keys():
                       comparison_dict[file_name.name] = {}
                    
                    # open evaluation file:
                    with open(file_name, "r") as f:
                        data = json.load(f)
                    comparison_dict[file_name.name][solution_method.name] = data["metadata"]["picked_instances"]
            
            for key, data in comparison_dict.items():
                release_times_list = [release_times for key, release_times in data.items()]
                print(release_times_list)
                flag = all(lst == release_times_list[0] for lst in release_times_list) if release_times_list else True
                self.assertEqual(flag, True, f"{release_times_list}")






