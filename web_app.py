#!/usr/bin/env python3
from app.web.app import app


if __name__ == "__main__":
    app.run(debug=True, port=5010)
