from job_hunt_agent.rendering import markdown_to_html


def test_markdown_renderer_escapes_and_preserves_structure():
    rendered = markdown_to_html("# Draft\n\n- Verified fact\n\n<script>alert(1)</script>")
    assert "<h1>Draft</h1>" in rendered
    assert "<li>Verified fact</li>" in rendered
    assert "<ul><li>Verified fact</li></ul>" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>alert(1)</script>" not in rendered

