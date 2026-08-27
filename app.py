from __future__ import annotations

import streamlit as st


def main() -> None:
    page = st.navigation(
        [
            st.Page(
                "pages/1_Generate_Resume.py", title="Generate Resume",
                icon=":material/description:", url_path="generate-resume", default=True,
            ),
            st.Page(
                "pages/2_Tracker.py", title="Tracker",
                icon=":material/list_alt:", url_path="tracker",
            ),
        ],
        position="sidebar",
    )
    page.run()


if __name__ == "__main__":
    main()
