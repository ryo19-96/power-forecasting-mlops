from typing import List
import category_encoders as ce
import pandas as pd


class FeatureEncoder:
    """
    category_encoderに実装されているEncoderをラップするクラス
    One-Hot EncodingとOrdinal Encodingに対応
    """

    def __init__(self, name: str, columns: List[str]) -> None:
        """
        Args:
            name (str): Encoderの仕方を指定
            columns (List[str]): エンコードするカラム
        """
        self.name = name
        self.columns = columns
        self.fitted = False

        if self.name == "One-Hot":
            self.encoder = ce.OneHotEncoder(cols=self.columns, use_cat_names=True)
        elif self.name == "Ordinal":
            self.encoder = ce.OrdinalEncoder(cols=self.columns)

    def fit_transform(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """
        fitとtransformを同時に行う
        Args:
            input_df (pd.DataFrame): エンコードするデータ
        Returns:
            pd.DataFrame: エンコードされたデータ
        """
        self.fit(input_df)
        return self.transform(input_df)

    def fit(self, input_df: pd.DataFrame) -> None:
        """
        fitのみを行いたい場合
        Args:
            input_df (pd.DataFrame): エンコードするデータ
        """
        self.encoder.fit(input_df)
        self.fitted = True

    def transform(self, input_df: pd.DataFrame) -> pd.DataFrame:
        """
        対象となる列に対象のエンコーダーを適用する
        Args:
            input_df (pd.DataFrame): エンコードするデータ
        Returns:
            pd.DataFrame: エンコードされたデータ
        """
        return self.encoder.transform(input_df)
