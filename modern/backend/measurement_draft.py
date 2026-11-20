"""A records editor draft, accepted as one project operation like GTK's dialog."""

import copy
from estimator.data.measurement import MeasurementItemCustom


class MeasurementDraft:
    def __init__(self, editor, identity):
        editor.ensure_ids()
        if identity not in editor.ids:
            raise ValueError("Select a measurement item")
        self.identity = identity
        self.item = copy.deepcopy(editor.db.get_measurement().items[editor.ids.index(identity)])
        if not isinstance(self.item, MeasurementItemCustom):
            raise ValueError("Select a custom measurement item")
        self.saved = copy.deepcopy(self.item.get_model())
        self.saved_ids = editor.record_ids[identity][:]
        self.history, self.future = [], []

    @property
    def dirty(self):
        return self.item.get_model() != self.saved

    def state(self):
        return dict(id=self.identity, dirty=self.dirty, undo=bool(self.history), redo=bool(self.future))

    def snapshot(self, editor):
        return copy.deepcopy(self.item), editor.record_ids[self.identity][:]

    def restore(self, editor, snapshot):
        self.item, editor.record_ids[self.identity] = copy.deepcopy(snapshot)

    def mutate(self, editor, action):
        before = self.snapshot(editor)
        clipboard = copy.deepcopy(editor.clipboard)
        try:
            result = action()
        except Exception:
            self.restore(editor, before)
            editor.clipboard = clipboard
            raise
        if self.item.get_model() != before[0].get_model():
            self.history.append(before)
            self.history = self.history[-100:]
            self.future.clear()
            editor.owner.revision += 1
        return result

    def travel(self, editor, redo=False):
        source, target = (self.future, self.history) if redo else (self.history, self.future)
        if source:
            target.append(self.snapshot(editor))
            self.restore(editor, source.pop())
            editor.owner.revision += 1

    def write(self, editor, db):
        meas = db.get_measurement()
        meas.items[editor.ids.index(self.identity)] = copy.deepcopy(self.item)
        db.set_measurement(meas)

    def accept(self, editor):
        if self.dirty:
            # The project undo snapshot must contain the original record identities.
            current_ids = editor.record_ids[self.identity][:]
            editor.record_ids[self.identity] = self.saved_ids[:]
            try:
                editor.mutate(lambda: self.write(editor, editor.db), reload=False, preserve_records=True)
            finally:
                editor.record_ids[self.identity] = current_ids
            editor.owner.revision += 1
        self.saved = copy.deepcopy(self.item.get_model())
        self.saved_ids = editor.record_ids[self.identity][:]
        self.history.clear()
        self.future.clear()
