"""
A package to attempt making serialization of Django objects easier with 
better support for objects to dictionaries, to json, and other formats.
It attempts to make serialization "smart" without having to write our own
custom parser for each object. Basically the goal is to make the separate parts
usable in other applications than simply serializing the data, but still have
easy to use functions that will serialize the data to any format that it
detects. 
"""