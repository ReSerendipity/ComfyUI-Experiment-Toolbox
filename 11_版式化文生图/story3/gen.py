# -*- coding: utf-8 -*-
"""《便利店的第七年》· 生成入口

薄壳：真正的逻辑在 `../story_kit.py`。

  python gen.py --plan
  python gen.py
  python gen.py 3 5
  python gen.py --index
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import story_kit

if __name__ == "__main__":
    sys.exit(story_kit.main([os.path.join(HERE, "story_data.py")] + sys.argv[1:]))
