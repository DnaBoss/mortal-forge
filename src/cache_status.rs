use std::{fs::File, io::Read, path::Path};

use serde_json::{Value, json};

pub fn read_receipt(path: &Path) -> Result<Value, String> {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(json!({"ok": false, "reason": "No cache receipt yet"}));
        }
        Err(error) => return Err(error.to_string()),
    };
    let mut contents = String::new();
    file.take(1_000_001)
        .read_to_string(&mut contents)
        .map_err(|error| error.to_string())?;
    if contents.len() > 1_000_000 {
        return Err("Cache receipt too large".into());
    }
    serde_json::from_str(&contents).map_err(|error| error.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_receipt_is_explicit() {
        let dir = tempfile::tempdir().unwrap();
        let result = read_receipt(&dir.path().join("missing.json")).unwrap();
        assert_eq!(result["ok"], false);
    }

    #[test]
    fn rejects_oversized_and_malformed_receipts() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("status.json");
        std::fs::write(&path, vec![b' '; 1_000_001]).unwrap();
        assert!(read_receipt(&path).is_err());
        std::fs::write(&path, "not-json").unwrap();
        assert!(read_receipt(&path).is_err());
        std::fs::write(&path, r#"{"duplicates":[],"skipped":["busy"]}"#).unwrap();
        assert_eq!(read_receipt(&path).unwrap()["skipped"][0], "busy");
    }
}
