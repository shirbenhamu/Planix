from src.parsers.base_parser import BaseParser
from src.parsers.text_file_parser import TextFileParser

class ParserFactory:
    # Static method to create a parser instance based on the specified file type
    @staticmethod
    def create_parser(file_type: str) -> BaseParser:
        if file_type.lower() == "txt":
            return TextFileParser()
        
        # add more parser options here when needed, e.g.:
        # elif file_type.lower() == "json":
        #    return JsonFileParser()
        
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        