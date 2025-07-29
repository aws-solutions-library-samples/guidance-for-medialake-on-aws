export const notifyError = (message: string) => {
  console.error(message);
  // You can replace this with a proper notification system like react-toastify
  alert(message);
};

export const notifySuccess = (message: string) => {
  console.log(message);
  // You can replace this with a proper notification system like react-toastify
  alert(message);
};
