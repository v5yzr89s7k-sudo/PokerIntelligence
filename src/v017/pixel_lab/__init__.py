"""
V0.17 Pixel Laboratory.

The Pixel Lab is a black-box visual validation environment.

Architecture:

    deterministic private truth
              |
              v
        table renderer
              |
              v
         image frames
              |
       HARD ISOLATION WALL
              |
              v
     production observer
              |
              v
       current_hand.txt
              |
              v
      offline comparator

The observer side must never receive simulator truth.
"""
