"""Gradio UI. Depends only on interfaces.py and factory.py for DI."""

import gradio as gr

import factory
from orchestrator import Session, turn

CSS = """
.gradio-container { max-width: 100% !important; padding: 16px; }
#chat-column, #side-column { height: 100%; }
#chatbot { flex-grow: 1; }
#inspector { flex-grow: 1; }
"""

INTRO_MESSAGE = (
    "Hi, I'm here to chat with you and get to know you a bit. "
    "Feel free to talk naturally -- I'll ask about anything I'm missing as we go."
)


def _new_session() -> Session:
    schema = factory.make_schema()
    return Session(
        schema=schema,
        graph=factory.make_graph(schema),
        extractor=factory.make_extractor(),
        generator=factory.make_generator(),
    )


def _render_inspector(snapshot: dict) -> str:
    lines = []
    for key, entry in snapshot.items():
        if entry["acquired"]:
            lines.append(f"✓ {key}: {entry['value']}")
        else:
            lines.append(f"· {key}: (missing)")
    return "\n".join(lines)


def _add_user_message(message: str, chat_history: list):
    chat_history = chat_history + [{"role": "user", "content": message}]
    return chat_history, "", message


def _bot_respond(message: str, chat_history: list, session: Session):
    if session is None:
        session = _new_session()
    result = turn(session, message)
    chat_history = chat_history + [{"role": "assistant", "content": result["reply"]}]
    inspector_text = _render_inspector(result["slots"])
    return chat_history, session, inspector_text


def _reset_fn():
    session = _new_session()
    inspector_text = _render_inspector(session.graph.snapshot())
    chat_history = [{"role": "assistant", "content": INTRO_MESSAGE}]
    return chat_history, session, inspector_text


with gr.Blocks(title="Graph demo", fill_height=True, css=CSS) as demo:
    gr.Markdown("# Graph demo")
    session_state = gr.State(None)
    pending_msg = gr.State("")

    with gr.Row(equal_height=True):
        with gr.Column(scale=3, elem_id="chat-column"):
            gr.Markdown("### Chat")
            chatbot = gr.Chatbot(label="Chat", elem_id="chatbot", scale=1)
            with gr.Row():
                msg_box = gr.Textbox(
                    label="Message",
                    placeholder="Type a message...",
                    scale=4,
                    show_label=False,
                )
                send_btn = gr.Button("Send", scale=1)
        with gr.Column(scale=1, elem_id="side-column"):
            gr.Markdown("### Graph state")
            inspector = gr.Textbox(
                label="Graph state",
                elem_id="inspector",
                interactive=False,
                scale=1,
                show_label=False,
            )
            reset_btn = gr.Button("Reset session")

    send_btn.click(
        _add_user_message,
        inputs=[msg_box, chatbot],
        outputs=[chatbot, msg_box, pending_msg],
    ).then(
        _bot_respond,
        inputs=[pending_msg, chatbot, session_state],
        outputs=[chatbot, session_state, inspector],
    )
    msg_box.submit(
        _add_user_message,
        inputs=[msg_box, chatbot],
        outputs=[chatbot, msg_box, pending_msg],
    ).then(
        _bot_respond,
        inputs=[pending_msg, chatbot, session_state],
        outputs=[chatbot, session_state, inspector],
    )
    reset_btn.click(
        _reset_fn,
        inputs=[],
        outputs=[chatbot, session_state, inspector],
    )
    demo.load(_reset_fn, inputs=[], outputs=[chatbot, session_state, inspector])
